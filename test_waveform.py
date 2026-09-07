import io
import json
import math
import struct
import unittest
import zipfile
from waveform import build, encode_tfw, parse_tfw, package, expression


class WaveformTests(unittest.TestCase):
    def spec(self, **kw):
        return dict(dict(mode='formula', formula='sin(2*pi*u)', points=4,
                         period=1, vpp=2, offset=0), **kw)

    def test_sine_sampling_and_codes(self):
        y,c,m=build(self.spec())
        for a,b in zip(y,[0,1,0,-1]): self.assertAlmostEqual(a,b)
        self.assertEqual(c,[8192,16383,8192,0])
        self.assertEqual(m['sample_interval_s'],.25)
        self.assertAlmostEqual(m['rms_normalized'],math.sqrt(.5))

    def test_periodic_endpoint_not_duplicated(self):
        y,_,_=build(self.spec(formula='u',points=2))
        self.assertEqual(y,[0,.5])

    def test_normalization_preserves_dc(self):
        y,_,m=build(self.spec(formula='2+2*u',normalize=True))
        self.assertEqual(m['normalization_divisor'],3.5)
        self.assertAlmostEqual(y[0],2/3.5)

    def test_csv_period_and_header(self):
        y,_,m=build(self.spec(mode='csv',csv='t;y\n5,0;0\n5,1;1\n5,2;-1',delimiter=';',header=True))
        self.assertEqual(y,[0,1,-1])
        self.assertAlmostEqual(m['period_s'],.3)

    def test_bad_csv(self):
        for text in ['0,1\n0,2', '0,1\n1,0\n3,-1', '0,1\n1,nan', '0,1\n1,0,3']:
            with self.assertRaises(ValueError):build(self.spec(mode='csv',csv=text))

    def test_nodes(self):
        y,_,_=build(self.spec(mode='nodes',nodes='0,0\n0.5,1\n1,0'))
        self.assertEqual(y,[0,.5,1,.5])

    def test_reject_formula_code(self):
        for expr in ['__import__("os")','(1).__class__','[1,2][0]','sum(x for x in [1])','2**1000','1/0','sqrt(-1)']:
            with self.assertRaises((ValueError,TypeError,ArithmeticError)):build(self.spec(formula=expr))

    def test_conditional(self):
        y,_,_=build(self.spec(formula='1 if u < 0.5 else -1'))
        self.assertEqual(y,[1,1,-1,-1])

    def test_invalid_settings(self):
        for kw in [dict(points=1),dict(points=4.5),dict(points=131073),dict(period=0),dict(vpp=0),dict(formula='2'),dict(offset='nan'),dict(period=1e-6,points=4096)]:
            with self.assertRaises(ValueError):build(self.spec(**kw))

    def test_binary_independent_offsets(self):
        b=encode_tfw([0,8192,16383])
        self.assertEqual(len(b),518)
        self.assertEqual(b[:16],b'TEKAFG3000'+b'\0'*6)
        self.assertEqual(struct.unpack('>II',b[16:24]),(20050114,3))
        self.assertEqual(b[512:],b'\x00\x00\x20\x00\x3f\xff')
        self.assertEqual(parse_tfw(b),[0,8192,16383])

    def test_template_preserved_and_mismatch(self):
        b=bytearray(encode_tfw([0,16383]));b[100:105]=b'TEST!'
        new=encode_tfw([100,200],bytes(b))
        self.assertEqual(new[:512],b[:512])
        with self.assertRaises(ValueError):encode_tfw([1,2,3],bytes(b))
        with self.assertRaises(ValueError):parse_tfw(new[:-1])

    def test_zip_settings_and_project(self):
        spec=self.spec()
        with zipfile.ZipFile(io.BytesIO(package(spec))) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(parse_tfw(z.read('ONDA.tfw')),[8192,16383,8192,0])
            self.assertEqual(json.loads(z.read('PROYECTO.json')),spec)
            self.assertEqual(json.loads(z.read('METADATOS.json'))['repeat_hz'],1)
            self.assertIn('NO',z.read('AJUSTES.txt').decode())


if __name__=='__main__':unittest.main()
