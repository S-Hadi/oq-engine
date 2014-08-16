import unittest
from openquake.commonlib import sap


def f(a, b, c, d=1):
    return [a, b, c, d]


class SapTestCase(unittest.TestCase):
    def test_ok(self):
        p = sap.Parser(f)
        p.arg('a', 'first argument')
        p.opt('b', 'second argument')
        p.flg('c', 'third argument')
        p.opt('d', 'fourth argument')
        self.assertEqual(
            ['1', '2', False, '3'], p.callfunc('1 -b=2 -d=3'.split()))

    def test_NameError(self):
        p = sap.Parser(f)
        p.arg('a', 'first argument')
        with self.assertRaises(NameError):
            p.flg('c', 'third argument')

    def test_help(self):
        p = sap.Parser(f)
        p.arg('a', 'first argument')
        p.opt('b', 'second argument')
        self.assertEqual(p.help(), '''\
usage: nosetests [-h] [-b B] a

positional arguments:
  a            first argument

optional arguments:
  -h, --help   show this help message and exit
  -b B, --b B  second argument
''')
        # missing argparse description for 'c' and 'd'
        with self.assertRaises(NameError):
            self.assertEqual(
                ['1', '2', False, '3'], p.callfunc('1 -b=2 -d=3'.split()))

    def test_long_argument(self):
        # test the replacement '_' -> '-' in variable names
        p = sap.Parser(lambda a_long_argument: None)
        p.opt('a_long_argument', 'a long argument')
        self.assertEqual(p.help(), '''\
usage: nosetests [-h] [-a A_LONG_ARGUMENT]

optional arguments:
  -h, --help            show this help message and exit
  -a A_LONG_ARGUMENT, --a-long-argument A_LONG_ARGUMENT
                        a long argument
''')
