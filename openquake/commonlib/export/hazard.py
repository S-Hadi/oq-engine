#  -*- coding: utf-8 -*-
#  vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright (c) 2014, GEM Foundation

#  OpenQuake is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.

#  OpenQuake is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.

#  You should have received a copy of the GNU Affero General Public License
#  along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import os
import collections

from openquake.commonlib.export import export
from openquake.commonlib.writers import scientificformat, fmt
from openquake.commonlib import hazard_writers
from openquake.hazardlib.imt import from_string


##################### export Ground Motion fields #############################

class GmfSet(object):
    """
    Small wrapper around the list of Gmf objects associated to the given SES.
    """
    def __init__(self, gmfset):
        self.gmfset = gmfset
        self.investigation_time = None
        self.stochastic_event_set_id = 1

    def __iter__(self):
        return iter(self.gmfset)

    def __nonzero__(self):
        return bool(self.gmfset)

    def __str__(self):
        return (
            'GMFsPerSES(investigation_time=%f, '
            'stochastic_event_set_id=%s,\n%s)' % (
                self.investigation_time,
                self.stochastic_event_set_id, '\n'.join(
                    sorted(str(g) for g in self.gmfset))))


class GroundMotionField(object):
    """
    The Ground Motion Field generated by the given rupture
    """
    def __init__(self, imt, sa_period, sa_damping, rupture_id, gmf_nodes):
        self.imt = imt
        self.sa_period = sa_period
        self.sa_damping = sa_damping
        self.rupture_id = rupture_id
        self.gmf_nodes = gmf_nodes

    def __iter__(self):
        return iter(self.gmf_nodes)

    def __getitem__(self, key):
        return self.gmf_nodes[key]

    def __str__(self):
        # string representation of a _GroundMotionField object showing the
        # content of the nodes (lon, lat an gmv). This is useful for debugging
        # and testing.
        mdata = ('imt=%(imt)s sa_period=%(sa_period)s '
                 'sa_damping=%(sa_damping)s rupture_id=%(rupture_id)s' %
                 vars(self))
        nodes = sorted(map(str, self.gmf_nodes))
        return 'GMF(%s\n%s)' % (mdata, '\n'.join(nodes))


Location = collections.namedtuple('Location', 'x y')


class GroundMotionFieldNode(object):
    # the signature is not (gmv, x, y) because the XML writer expects
    # a location object
    def __init__(self, gmv, loc):
        self.gmv = gmv
        self.location = loc

    def __lt__(self, other):
        """
        A reproducible ordering by lon and lat; used in
        :function:`openquake.commonlib.hazard_writers.gen_gmfs`
        """
        return self.location < other.location

    def __str__(self):
        """Return lon, lat and gmv of the node in a compact string form"""
        return '<X=%9.5f, Y=%9.5f, GMV=%9.7f>' % (
            self.location.x, self.location.y, self.gmv)


class GmfCollection(object):
    """
    Object converting the parameters

    :param sitecol: SiteCollection
    :rupture_tags: tags of the ruptures
    :gmfs_by_imt: dictionary of GMFs by IMT

    into an object with the right form for the EventBasedGMFXMLWriter.
    Iterating over a GmfCollection yields GmfSet objects.
    """
    def __init__(self, sitecol, rupture_tags, gmfs_by_imt):
        self.sitecol = sitecol
        self.rupture_tags = rupture_tags
        self.gmfs_by_imt = gmfs_by_imt

    def __iter__(self):
        gmfset = []
        for imt_str, gmfs in sorted(self.gmfs_by_imt.iteritems()):
            imt, sa_period, sa_damping = from_string(imt_str)
            for rupture_tag, gmf in zip(self.rupture_tags, gmfs.transpose()):
                nodes = (GroundMotionFieldNode(
                    gmv,
                    Location(site.location.longitude, site.location.latitude))
                    for site, gmv in zip(self.sitecol, gmf))
                gmfset.append(
                    GroundMotionField(
                        imt, sa_period, sa_damping, rupture_tag, nodes))
        yield GmfSet(gmfset)


@export.add('gmf_xml')
def export_gmf_xml(key, export_dir, sitecol, rupture_tags, gmfs):
    dest = os.path.join(export_dir, key.replace('_xml', '.xml'))
    writer = hazard_writers.EventBasedGMFXMLWriter(
        dest, sm_lt_path='', gsim_lt_path='')
    with fmt('%12.8E'):
        writer.serialize(GmfCollection(sitecol, rupture_tags, gmfs))
    return {key: dest}


@export.add('gmf_csv')
def export_gmf_csv(key, export_dir, sitecol, rupture_tags, gmfs):
    dest = os.path.join(export_dir, key.replace('_csv', '.csv'))
    with fmt('%12.8E'), open(dest, 'w') as f:
        for imt, gmf in gmfs.iteritems():
            for site, gmvs in zip(sitecol, gmf):
                row = [imt, site.location.longitude,
                       site.location.latitude] + list(gmvs)
                f.write(' '.join(map(scientificformat, row)) + '\n')
    return {key: dest}

######################## export hazard curves ##############################

HazardCurve = collections.namedtuple('HazardCurve', 'location poes')


@export.add('hazard_curves_csv')
def export_hazard_curves_csv(key, export_dir, sitecol, curves_by_imt):
    """
    Export the curves of the given realization into XML.

    :param key: output_type and export_type
    :param export_dir: the directory where to export
    :param sitecol: site collection
    :param rlz: realization instance
    :param curves_by_imt: dictionary with the curves keyed by IMT
    """
    dest = os.path.join(export_dir, key.replace('_csv', '.csv'))
    with fmt('%12.8E'), open(dest, 'w') as f:
        for imt, curves in sorted(curves_by_imt):
            for site, curve in zip(sitecol, curves_by_imt[imt]):
                row = [imt, site.location.longitude,
                       site.location.latitude] + list(curve)
                f.write(' '.join(map(scientificformat, row)) + '\n')
    return {key: dest}


@export.add('hazard_curves_xml')
def export_hazard_curves_xml(key, export_dir, sitecol, rlz, curves_by_imt,
                             imtls, investigation_time):
    """
    Export the curves of the given realization into XML.

    :param key: output_type and export_type
    :param export_dir: the directory where to export
    :param sitecol: site collection
    :param rlz: realization instance
    :param curves_by_imt: dictionary with the curves keyed by IMT
    :param imtls: dictionary with the intensity measure types and levels
    :param investigation_time: investigation time in years
    """
    smlt_path = '_'.join(rlz.sm_lt_path)
    gsimlt_path = '_'.join(rlz.gsim_lt_path)
    mdata = []
    hcurves = []
    for imt_str, imls in sorted(imtls.iteritems()):
        hcurves.append(
            [HazardCurve(site.location, poes)
             for site, poes in zip(sitecol, curves_by_imt[imt_str])])
        imt = from_string(imt_str)
        mdata.append({
            'quantile_value': None,
            'statistics': None,
            'smlt_path': smlt_path,
            'gsimlt_path': gsimlt_path,
            'investigation_time': investigation_time,
            'imt': imt[0],
            'sa_period': imt[1],
            'sa_damping': imt[2],
            'imls': imls,
        })
    dest = 'hazard_curve_multi-smltp_%s-gsimltp_%s.xml' % (
        smlt_path, gsimlt_path)
    writer = hazard_writers.MultiHazardCurveXMLWriter(dest, mdata)
    with fmt('%12.8E'):
        writer.serialize(hcurves)
    return {key: dest}
