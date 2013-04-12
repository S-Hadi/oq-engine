#  -*- coding: utf-8 -*-
#  vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright (c) 2013, GEM Foundation

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

import unittest
from django.db import connection
from openquake.engine.tools.pg_importer import PGImporter
from openquake.engine.db.models import Output, GmfCollection, OqJob

"""
Test that we can import a GmfCollection with the PGImporter
"""

# id owner_id oq_job_id display_name output_type last_update
output = '''\
$out1	1	\N	gmf-rlz	gmf	2013-04-11 03:08:46.797773
'''

# id output_id lt_realization_id
gmf_collection = '''\
$coll10	$out1	\N
'''

# id gmf_collection_id investigation_time ses_ordinal
gmf_set = '''\
$set1	$coll10	10	1
$set2	$coll10	10	2
$set3	$coll10	10	3
'''

# id gmf_set_id imt sa_period sa_damping gmvs rupture_ids result_grp_ordinal location
gmf = '''\
$gmf01	$set1	SA	0.1	5	{0.729799582246203}	{709346}	1	0101000020E610000000000000000000000000000000000000
$gmf02	$set1	SA	0.1	5	{0.0141248596268433}	{709346}	1	0101000020E61000000000000000000000000000000000E03F
$gmf03	$set1	PGA	\N	\N	{0.252294938306868}	{709346}	1	0101000020E610000000000000000000000000000000000000
$gmf04	$set1	PGA	\N	\N	{0.00894558476907965}	{709346}	1	0101000020E61000000000000000000000000000000000E03F
$gmf05	$set3	SA	0.1	5	{0.73468651581123}	{709348}	1	0101000020E610000000000000000000000000000000000000
$gmf06	$set3	SA	0.1	5	{0.130897324686063}	{709348}	1	0101000020E61000000000000000000000000000000000E03F
$gmf07	$set3	PGA	\N	\N	{0.23164352054727}	{709348}	1	0101000020E610000000000000000000000000000000000000
$gmf08	$set3	PGA	\N	\N	{0.0264362061113464}	{709348}	1	0101000020E61000000000000000000000000000000000E03F
$gmf09	$set1	SA	0.1	5	{0.0571210320882165,0.0851203442596857,0.0512935367105168}	{709350,709352,709354}	2	0101000020E610000000000000000000000000000000000000
$gmf10	$set1	SA	0.1	5	{0.0457237221727419,0.0250737105548348,0.0466984811965513}	{709350,709352,709354}	2	0101000020E61000000000000000000000000000000000E03F
$gmf11	$set1	PGA	\N	\N	{0.151132933300216,0.0477298423601717,0.0142826375129993}	{709350,709352,709354}	2	0101000020E610000000000000000000000000000000000000
$gmf12	$set1	PGA	\N	\N	{0.0720017584564812,0.0209473778737383,0.00810452525440645}	{709350,709352,709354}	2	0101000020E61000000000000000000000000000000000E03F
$gmf13	$set1	SA	0.1	5	{0.0647094509155515}	{709356}	3	0101000020E610000000000000000000000000000000000000
$gmf14	$set1	SA	0.1	5	{0.0137011674890562}	{709356}	3	0101000020E61000000000000000000000000000000000E03F
$gmf15	$set1	PGA	\N	\N	{0.053177248284009}	{709356}	3	0101000020E610000000000000000000000000000000000000
$gmf16	$set1	PGA	\N	\N	{0.014933592444171}	{709356}	3	0101000020E61000000000000000000000000000000000E03F
$gmf17	$set1	SA	0.1	5	{0.156892787041029}	{709358}	4	0101000020E610000000000000000000000000000000000000
$gmf18	$set1	SA	0.1	5	{0.015367505662649}	{709358}	4	0101000020E61000000000000000000000000000000000E03F
$gmf19	$set1	PGA	\N	\N	{0.0346846321726566}	{709358}	4	0101000020E610000000000000000000000000000000000000
$gmf20	$set1	PGA	\N	\N	{0.0247923869973088}	{709358}	4	0101000020E61000000000000000000000000000000000E03F
$gmf21	$set2	SA	0.1	5	{0.0168322906204596}	{709360}	4	0101000020E610000000000000000000000000000000000000
$gmf22	$set2	SA	0.1	5	{0.0267122052505091}	{709360}	4	0101000020E61000000000000000000000000000000000E03F
$gmf23	$set2	PGA	\N	\N	{0.00509134495333861}	{709360}	4	0101000020E610000000000000000000000000000000000000
$gmf24	$set2	PGA	\N	\N	{0.0187720473080453}	{709360}	4	0101000020E61000000000000000000000000000000000E03F
$gmf25	$set3	SA	0.1	5	{0.0174152488960141}	{709362}	4	0101000020E610000000000000000000000000000000000000
$gmf26	$set3	SA	0.1	5	{0.00365106296335889}	{709362}	4	0101000020E61000000000000000000000000000000000E03F
$gmf27	$set3	PGA	\N	\N	{0.00327192823764393}	{709362}	4	0101000020E610000000000000000000000000000000000000
$gmf28	$set3	PGA	\N	\N	{0.00257996694936015}	{709362}	4	0101000020E61000000000000000000000000000000000E03F
'''

imts = [('PGA', None, None), ('SA', 0.1, 5)]

num_tasks = 4

# expected stochastic event set 1
set1_exp = '''\
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709346
<X=0.0, Y=0.0, GMV=0.252294938307>
<X=0.0, Y=0.5, GMV=0.00894558476908>)
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709350
<X=0.0, Y=0.0, GMV=0.1511329333>
<X=0.0, Y=0.5, GMV=0.0720017584565>)
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709352
<X=0.0, Y=0.0, GMV=0.0477298423602>
<X=0.0, Y=0.5, GMV=0.0209473778737>)
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709354
<X=0.0, Y=0.0, GMV=0.014282637513>
<X=0.0, Y=0.5, GMV=0.00810452525441>)
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709356
<X=0.0, Y=0.0, GMV=0.053177248284>
<X=0.0, Y=0.5, GMV=0.0149335924442>)
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709358
<X=0.0, Y=0.0, GMV=0.0346846321727>
<X=0.0, Y=0.5, GMV=0.0247923869973>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709346
<X=0.0, Y=0.0, GMV=0.729799582246>
<X=0.0, Y=0.5, GMV=0.0141248596268>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709350
<X=0.0, Y=0.0, GMV=0.0571210320882>
<X=0.0, Y=0.5, GMV=0.0457237221727>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709352
<X=0.0, Y=0.0, GMV=0.0851203442597>
<X=0.0, Y=0.5, GMV=0.0250737105548>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709354
<X=0.0, Y=0.0, GMV=0.0512935367105>
<X=0.0, Y=0.5, GMV=0.0466984811966>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709356
<X=0.0, Y=0.0, GMV=0.0647094509156>
<X=0.0, Y=0.5, GMV=0.0137011674891>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709358
<X=0.0, Y=0.0, GMV=0.156892787041>
<X=0.0, Y=0.5, GMV=0.0153675056626>)'''

# expected stochastic event set 2
set2_exp = '''\
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709360
<X=0.0, Y=0.0, GMV=0.00509134495334>
<X=0.0, Y=0.5, GMV=0.018772047308>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709360
<X=0.0, Y=0.0, GMV=0.0168322906205>
<X=0.0, Y=0.5, GMV=0.0267122052505>)'''

# expected stochastic event set 3
set3_exp = '''\
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709348
<X=0.0, Y=0.0, GMV=0.231643520547>
<X=0.0, Y=0.5, GMV=0.0264362061113>)
GMF(imt=PGA sa_period=None sa_damping=None rupture_id=709362
<X=0.0, Y=0.0, GMV=0.00327192823764>
<X=0.0, Y=0.5, GMV=0.00257996694936>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709348
<X=0.0, Y=0.0, GMV=0.734686515811>
<X=0.0, Y=0.5, GMV=0.130897324686>)
GMF(imt=SA sa_period=0.1 sa_damping=5.0 rupture_id=709362
<X=0.0, Y=0.0, GMV=0.017415248896>
<X=0.0, Y=0.5, GMV=0.00365106296336>)'''


class PGImporterTestCase(unittest.TestCase):
    def testImportGmfCollection(self):
        connection.cursor()  # open the connection
        imp = PGImporter(connection.connection)
        imp.import_all([
            ('uiapi.output', output),
            ('hzrdr.gmf_collection', gmf_collection),
            ('hzrdr.gmf_set', gmf_set),
            ('hzrdr.gmf', gmf),
        ])
        out = Output.objects.latest('id')
        out.oq_job = OqJob.objects.create(owner_id=1)  # fake job
        # the fake job is unfortunately needed in GmfSet.iter_gmfs
        out.save()
        [coll] = GmfCollection.objects.filter(output=out)
        set1, set2, set3 = list(coll)
        set1_str = '\n'.join(
            map(str, set1.iter_gmfs(num_tasks=num_tasks, imts=imts)))
        set2_str = '\n'.join(
            map(str, set2.iter_gmfs(num_tasks=num_tasks, imts=imts)))
        set3_str = '\n'.join(
            map(str, set3.iter_gmfs(num_tasks=num_tasks, imts=imts)))
        self.assertEqual(set1_str, set1_exp)
        self.assertEqual(set2_str, set2_exp)
        self.assertEqual(set3_str, set3_exp)
