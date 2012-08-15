# Copyright (c) 2010-2012, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import random

import nhlib.source
import numpy.random

from nhlib import correlation
from nhlib.calc import stochastic
from nhlib.calc import gmf as gmf_calc
from nhlib.calc import filters

from openquake import logs
from openquake.calculators.hazard import general as haz_general
from openquake.db import models
from openquake.input import logictree
from openquake.job.validation import MAX_SINT_32
from openquake.utils import stats
from openquake.utils import tasks as utils_tasks

#: Ground motion correlation model map
GM_CORRELATION_MODEL_MAP = {
    'JB2009': correlation.JB2009CorrelationModel,
}

#: Always 1 for the computation of ground motion fields in the event-based
#: hazard calculator.
DEFAULT_GMF_REALIZATIONS = 1


@utils_tasks.oqtask
@stats.progress_indicator('h')
def ses_and_gmfs(job_id, lt_rlz_id, src_ids, task_seed):
    """
    Celery task for the stochastic event set calculator.

    Samples logic trees and calls the stochastic event set calculator.

    Once stochastic event sets are calculated, results will be saved to the
    database. See :class:`openquake.db.models.SESCollection`.

    Optionally (specified in the job configuration using the
    `ground_motion_fields` parameter), GMFs can be computed from each rupture
    in each stochastic event set. GMFs are also saved to the database.

    Once all of this work is complete, a signal will be sent via AMQP to let
    the control noe know that the work is complete. (If there is any work left
    to be dispatched, this signal will indicate to the control node that more
    work can be enqueued.)

    :param int job_id:
        ID of the currently running job.
    :param lt_rlz_id:
        Id of logic tree realization model to calculate for.
    :param src_ids:
        List of ids of parsed source models from which we will generate
        stochastic event sets/ruptures.
    :param int task_seed:
        Value for seeding numpy/scipy in the computation of stochastic event
        sets and ground motion fields.
    """
    logs.LOG.info(('> starting `stochastic_event_sets` task: job_id=%s, '
                   'lt_realization_id=%s') % (job_id, lt_rlz_id))
    numpy.random.seed(task_seed)

    hc = models.HazardCalculation.objects.get(oqjob=job_id)

    lt_rlz = models.LtRealization.objects.get(id=lt_rlz_id)
    ltp = logictree.LogicTreeProcessor(hc.id)

    apply_uncertainties = ltp.parse_source_model_logictree_path(
            lt_rlz.sm_lt_path)
    gsims = ltp.parse_gmpe_logictree_path(lt_rlz.gsim_lt_path)

    sources = haz_general.gen_sources(
        src_ids, apply_uncertainties, hc.rupture_mesh_spacing,
        hc.width_of_mfd_bin, hc.area_source_discretization)

    if hc.ground_motion_fields:
        # The site collection is only needed for GMF calculation
        # (not for SES calculation).
        site_coll = haz_general.get_site_collection(hc)

    ses = models.SES.objects.get(ses_collection__lt_realization=lt_rlz)

    for _ in xrange(hc.ses_per_logic_tree_path):
        ses_poissonian = stochastic.stochastic_event_set_poissonian(
            sources, hc.investigation_time)

        for rupture in ses_poissonian:
            # Save SES ruptures to the db:
            # TODO: bulk insertion of ruptures?
            is_from_fault_source = rupture.source_typology in (
                nhlib.source.ComplexFaultSource,
                nhlib.source.SimpleFaultSource)

            lons = None
            lats = None
            depths = None

            if is_from_fault_source:
                # simple or complex fault:
                # geometry represented by a mesh
                lons = rupture.surface.lons
                lats = rupture.surface.lats
                depths = rupture.surface.depths
            else:
                pass
                # TODO: Deal with all of the source types

            models.SESRupture.objects.create(
                ses=ses,
                magnitude=rupture.mag,
                strike=rupture.surface.get_strike(),
                dip=rupture.surface.get_dip(),
                rake=rupture.rake,
                tectonic_region_type=rupture.tectonic_region_type,
                is_from_fault_source=is_from_fault_source,
                lons=lons,
                lats=lats,
                depths=depths,
            )


            if hc.ground_motion_fields:
                # Compute and save ground motion fields
                imts = [haz_general.imt_to_nhlib(x) for x in
                        hc.intensity_measure_types]

                correl_matrices = None
                if hc.ground_motion_correlation_model is not None:
                    # Compute correlation matrices
                    correl_model_cls = getattr(
                        correlation,
                        '%sCorrelationModel' \
                            % hc.ground_motion_correlation_model,
                        None)
                    if correl_model_cls is None:
                        raise RuntimeError(
                            "Unknown correlation model: '%s'"
                            % hc.ground_motion_correlation_model)

                    correl_model = correl_model_cls(
                        **hc.ground_motion_correlation_params)
                    correl_matrices= dict(
                        (imt,
                         correl_model.get_correlation_matrix(site_coll, imt))
                        for imt in imts)

                gmf_calc_kwargs = {
                    'rupture': rupture,
                    'sites': site_coll,
                    'imts': imts,
                    'gsim': gsims[rupture.tectonic_region_type],
                    'truncation_level': hc.truncation_level,
                    'realizations': DEFAULT_GMF_REALIZATIONS,
                    'lt_correlation_matrices': correl_matrices,
                    'rupture_site_filter':
                        filters.rupture_site_distance_filter(
                            hc.maximum_distance),
                }
                gmfs = gmf_calc.ground_motion_fields(**gmf_calc_kwargs)
                print gmfs
                # TODO: save gmfs to db

    # TODO: signal task completed


@staticmethod
def event_based_task_arg_gen(hc, job, sources_per_task, progress):
    """
    Loop through realizations and sources to generate a sequence of
    task arg tuples. Each tuple of args applies to a single task.

    Yielded results are quadruples of (job_id, realization_id,
    source_id_list, random_seed). (random_seed will be used to seed
    numpy for temporal occurence sampling.)

    :param hc:
        :class:`openquake.db.models.HazardCalculation` instance.
    :param job:
        :class:`openquake.db.models.OqJob` instance.
    :param int sources_per_task:
        The (max) number of sources to consider for each task.
    :param dict progress:
        A dict containing two integer values: 'total' and 'computed'. The task
        arg generator will update the 'total' count as the generator creates
        arguments.
    """

    rnd = random.Random()
    rnd.seed(hc.random_seed)

    realizations = models.LtRealization.objects.filter(
            hazard_calculation=hc, is_complete=False)

    for lt_rlz in realizations:
        source_progress = models.SourceProgress.objects.filter(
                is_complete=False, lt_realization=lt_rlz)
        source_ids = source_progress.values_list('parsed_source_id',
                                                 flat=True)
        progress['total'] += len(source_ids)

        for offset in xrange(0, len(source_ids), sources_per_task):
            # Since this seed will used for numpy random seeding, it needs to
            # positive (since numpy will convert it to a unsigned long).
            task_seed = rnd.randint(0, MAX_SINT_32)
            task_args = (job.id, lt_rlz.id,
                         source_ids[offset:offset + sources_per_task],
                         task_seed)
            yield task_args


class EventBasedHazardCalculator(haz_general.BaseHazardCalculatorNext):
    """
    Probabilistic Event-Based hazard calculator. Computes stochastic event sets
    and (optionally) ground motion fields.
    """

    core_calc_task = ses_and_gmfs
    task_arg_gen = event_based_task_arg_gen

    def initialize_ses_db_records(self, lt_rlz):
        """
        Create :class:`~openquake.db.models.Output`,
        :class:`~openquake.db.models.SESCollection` and
        :class:`~openquake.db.models.SES` "container" records for a single
        realization.

        Stochastic event set ruptures computed for this realization will be
        associated to these containers.
        """
        hc = self.job.hazard_calculation

        output = models.Output.objects.create(
            owner=self.job.owner,
            oq_job=self.job,
            display_name='ses-coll-rlz-%s' % lt_rlz.id,
            output_type='ses')

        ses_coll = models.SESCollection.objects.create(
            output=output, lt_realization=lt_rlz)

        ses = models.SES.objects.create(
            ses_collection=ses_coll, investigation_time=hc.investigation_time)

    def initialize_gmf_db_records(self, lt_rlz):
        """
        Create :class:`~openquake.db.models.Output`,
        :class:`~openquake.db.models.GmfCollection` and
        :class:`~openquake.db.models.GmfSet` "container" records for a single
        realization.

        GMFs for this realization will be associated to these containers.
        """
        hc = self.job.hazard_calculation

        output = models.Output.objects.create(
            owner=self.job.owner,
            oq_job=self.job,
            display_name='gmf-rlz-%s' % lt_rlz.id,
            output_type='gmf')

        gmf_coll = models.GmfCollection.objects.create(
            output=output, lt_realization=lt_rlz)

        gmf_set = models.GmfSet.objects.create(
            gmf_collection=gmf_coll, investigation_time=hc.investigation_time)

    def pre_execute(self):
        """
        Do pre-execution work. At the moment, this work entails: parsing and
        initializing sources, parsing and initializing the site model (if there
        is one), and generating logic tree realizations. (The latter piece
        basically defines the work to be done in the `execute` phase.)
        """

        # Parse logic trees and create source Inputs.
        self.initialize_sources()

        # Deal with the site model and compute site data for the calculation
        # (if a site model was specified, that is).
        # This is only necessary if the user has chosen to compute GMFs
        # (in addition to stochastic event sets).
        if self.job.hazard_calculation.ground_motion_fields:
            self.initialize_site_model()

        # Now bootstrap the logic tree realizations and related data.
        # This defines for us the "work" that needs to be done when we reach
        # the `execute` phase.
        rlz_callbacks = [self.initialize_ses_db_records]
        if self.job.hazard_calculation.ground_motion_fields:
            rlz_callbacks.append(self.initialize_gmf_db_records)

        self.initialize_realizations(rlz_callbacks=rlz_callbacks)

    def post_execute(self):
        # TODO: implement me
        print "post_execute"

    def post_process(self):
        # TODO: implement me
        print "post_process"
