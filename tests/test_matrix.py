from talent_observatory.warehouse.engine import WarehouseEngine

import unittest

class MatrixTests(unittest.TestCase):
    def setUp(self): self.engine=WarehouseEngine()
    def test_case_1_1(self):
        subject={'id':'case-1-1','values':[1,1,1],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_2(self):
        subject={'id':'case-1-2','values':[1,2,2],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_3(self):
        subject={'id':'case-1-3','values':[1,3,3],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_4(self):
        subject={'id':'case-1-4','values':[1,4,4],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_5(self):
        subject={'id':'case-1-5','values':[1,5,5],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_6(self):
        subject={'id':'case-1-6','values':[1,6,6],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_7(self):
        subject={'id':'case-1-7','values':[1,7,7],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_8(self):
        subject={'id':'case-1-8','values':[1,8,8],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_9(self):
        subject={'id':'case-1-9','values':[1,9,9],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_10(self):
        subject={'id':'case-1-10','values':[1,10,10],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_11(self):
        subject={'id':'case-1-11','values':[1,11,11],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_1_12(self):
        subject={'id':'case-1-12','values':[1,12,12],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':21,'reserved':1,'threshold':1})
        self.assertEqual(result.key,'case-1-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_1(self):
        subject={'id':'case-2-1','values':[2,1,2],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_2(self):
        subject={'id':'case-2-2','values':[2,2,4],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_3(self):
        subject={'id':'case-2-3','values':[2,3,6],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_4(self):
        subject={'id':'case-2-4','values':[2,4,8],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_5(self):
        subject={'id':'case-2-5','values':[2,5,10],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_6(self):
        subject={'id':'case-2-6','values':[2,6,12],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_7(self):
        subject={'id':'case-2-7','values':[2,7,14],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_8(self):
        subject={'id':'case-2-8','values':[2,8,16],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_9(self):
        subject={'id':'case-2-9','values':[2,9,18],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_10(self):
        subject={'id':'case-2-10','values':[2,10,20],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_11(self):
        subject={'id':'case-2-11','values':[2,11,22],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_2_12(self):
        subject={'id':'case-2-12','values':[2,12,24],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':22,'reserved':2,'threshold':2})
        self.assertEqual(result.key,'case-2-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_1(self):
        subject={'id':'case-3-1','values':[3,1,3],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_2(self):
        subject={'id':'case-3-2','values':[3,2,6],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_3(self):
        subject={'id':'case-3-3','values':[3,3,9],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_4(self):
        subject={'id':'case-3-4','values':[3,4,12],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_5(self):
        subject={'id':'case-3-5','values':[3,5,15],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_6(self):
        subject={'id':'case-3-6','values':[3,6,18],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_7(self):
        subject={'id':'case-3-7','values':[3,7,21],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_8(self):
        subject={'id':'case-3-8','values':[3,8,24],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_9(self):
        subject={'id':'case-3-9','values':[3,9,27],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_10(self):
        subject={'id':'case-3-10','values':[3,10,30],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_11(self):
        subject={'id':'case-3-11','values':[3,11,33],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_3_12(self):
        subject={'id':'case-3-12','values':[3,12,36],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':23,'reserved':3,'threshold':3})
        self.assertEqual(result.key,'case-3-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_1(self):
        subject={'id':'case-4-1','values':[4,1,4],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_2(self):
        subject={'id':'case-4-2','values':[4,2,8],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_3(self):
        subject={'id':'case-4-3','values':[4,3,12],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_4(self):
        subject={'id':'case-4-4','values':[4,4,16],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_5(self):
        subject={'id':'case-4-5','values':[4,5,20],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_6(self):
        subject={'id':'case-4-6','values':[4,6,24],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_7(self):
        subject={'id':'case-4-7','values':[4,7,28],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_8(self):
        subject={'id':'case-4-8','values':[4,8,32],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_9(self):
        subject={'id':'case-4-9','values':[4,9,36],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_10(self):
        subject={'id':'case-4-10','values':[4,10,40],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_11(self):
        subject={'id':'case-4-11','values':[4,11,44],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_4_12(self):
        subject={'id':'case-4-12','values':[4,12,48],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':24,'reserved':0,'threshold':4})
        self.assertEqual(result.key,'case-4-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_1(self):
        subject={'id':'case-5-1','values':[5,1,5],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_2(self):
        subject={'id':'case-5-2','values':[5,2,10],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_3(self):
        subject={'id':'case-5-3','values':[5,3,15],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_4(self):
        subject={'id':'case-5-4','values':[5,4,20],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_5(self):
        subject={'id':'case-5-5','values':[5,5,25],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_6(self):
        subject={'id':'case-5-6','values':[5,6,30],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_7(self):
        subject={'id':'case-5-7','values':[5,7,35],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_8(self):
        subject={'id':'case-5-8','values':[5,8,40],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_9(self):
        subject={'id':'case-5-9','values':[5,9,45],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_10(self):
        subject={'id':'case-5-10','values':[5,10,50],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_11(self):
        subject={'id':'case-5-11','values':[5,11,55],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_5_12(self):
        subject={'id':'case-5-12','values':[5,12,60],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':25,'reserved':1,'threshold':5})
        self.assertEqual(result.key,'case-5-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_1(self):
        subject={'id':'case-6-1','values':[6,1,6],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_2(self):
        subject={'id':'case-6-2','values':[6,2,12],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_3(self):
        subject={'id':'case-6-3','values':[6,3,18],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_4(self):
        subject={'id':'case-6-4','values':[6,4,24],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_5(self):
        subject={'id':'case-6-5','values':[6,5,30],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_6(self):
        subject={'id':'case-6-6','values':[6,6,36],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_7(self):
        subject={'id':'case-6-7','values':[6,7,42],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_8(self):
        subject={'id':'case-6-8','values':[6,8,48],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_9(self):
        subject={'id':'case-6-9','values':[6,9,54],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_10(self):
        subject={'id':'case-6-10','values':[6,10,60],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_11(self):
        subject={'id':'case-6-11','values':[6,11,66],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_6_12(self):
        subject={'id':'case-6-12','values':[6,12,72],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':26,'reserved':2,'threshold':6})
        self.assertEqual(result.key,'case-6-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_1(self):
        subject={'id':'case-7-1','values':[7,1,7],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_2(self):
        subject={'id':'case-7-2','values':[7,2,14],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_3(self):
        subject={'id':'case-7-3','values':[7,3,21],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_4(self):
        subject={'id':'case-7-4','values':[7,4,28],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_5(self):
        subject={'id':'case-7-5','values':[7,5,35],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_6(self):
        subject={'id':'case-7-6','values':[7,6,42],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_7(self):
        subject={'id':'case-7-7','values':[7,7,49],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_8(self):
        subject={'id':'case-7-8','values':[7,8,56],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_9(self):
        subject={'id':'case-7-9','values':[7,9,63],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_10(self):
        subject={'id':'case-7-10','values':[7,10,70],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_11(self):
        subject={'id':'case-7-11','values':[7,11,77],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_7_12(self):
        subject={'id':'case-7-12','values':[7,12,84],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':27,'reserved':3,'threshold':7})
        self.assertEqual(result.key,'case-7-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_1(self):
        subject={'id':'case-8-1','values':[8,1,8],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-1')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_2(self):
        subject={'id':'case-8-2','values':[8,2,16],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-2')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_3(self):
        subject={'id':'case-8-3','values':[8,3,24],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-3')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_4(self):
        subject={'id':'case-8-4','values':[8,4,32],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-4')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_5(self):
        subject={'id':'case-8-5','values':[8,5,40],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-5')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_6(self):
        subject={'id':'case-8-6','values':[8,6,48],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-6')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_7(self):
        subject={'id':'case-8-7','values':[8,7,56],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-7')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_8(self):
        subject={'id':'case-8-8','values':[8,8,64],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-8')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_9(self):
        subject={'id':'case-8-9','values':[8,9,72],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-9')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_10(self):
        subject={'id':'case-8-10','values':[8,10,80],'demand':2}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-10')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_11(self):
        subject={'id':'case-8-11','values':[8,11,88],'demand':3}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-11')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})

    def test_case_8_12(self):
        subject={'id':'case-8-12','values':[8,12,96],'demand':1}
        result=self.engine.evaluate(subject,{'capacity':28,'reserved':0,'threshold':8})
        self.assertEqual(result.key,'case-8-12')
        self.assertGreaterEqual(result.value,0)
        self.assertIn(result.accepted,{True,False})
