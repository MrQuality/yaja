"""Safety gates for the opt-in native database verifier."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'check_postgresql', Path(__file__).resolve().parents[1] / 'scripts/check_postgresql.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ContainerBoundaryTests(unittest.TestCase):
    def valid(self):
        return {
            'State': {'Running': True},
            'Config': {'Labels': {'purpose': 'kehila-postgresql-test'}, 'Image': check.IMAGE},
            'HostConfig': {'NetworkMode': 'none', 'PortBindings': {}, 'Privileged': False,
                           'Binds': [], 'Memory': 256 * 1024**2, 'NanoCpus': 10**9,
                           'PidsLimit': 128,
                           'Tmpfs': {'/var/lib/postgresql/data': 'rw,size=256m,nosuid,nodev'}},
            'Mounts': [],
        }

    def test_explicit_ephemeral_container_accepted(self):
        check.validate_container(self.valid())

    def test_unsafe_container_rejected_before_database_work(self):
        cases = [
            ('State', 'Running', False),
            ('Config', 'Labels', {}),
            ('Config', 'Image', 'postgres:latest'),
            ('HostConfig', 'NetworkMode', 'bridge'),
            ('HostConfig', 'PortBindings', {'5432/tcp': [{}]}),
            ('HostConfig', 'Privileged', True),
            ('HostConfig', 'Binds', ['/data:/var/lib/postgresql/data']),
            ('HostConfig', 'Memory', 0),
            ('HostConfig', 'Memory', 512 * 1024**2),
            ('HostConfig', 'NanoCpus', 0),
            ('HostConfig', 'NanoCpus', 2 * 10**9),
            ('HostConfig', 'PidsLimit', -1),
            ('HostConfig', 'PidsLimit', 256),
            ('HostConfig', 'Tmpfs', {}),
            ('HostConfig', 'Tmpfs', {'/var/lib/postgresql/data': 'rw,size=2g'}),
        ]
        for section, key, value in cases:
            with self.subTest(section=section, key=key, value=value):
                info = copy.deepcopy(self.valid())
                info[section][key] = value
                with self.assertRaises(ValueError):
                    check.validate_container(info)
        info = self.valid()
        info['Mounts'] = [{'Type': 'volume', 'Destination': '/var/lib/postgresql/data'}]
        with self.assertRaises(ValueError):
            check.validate_container(info)


if __name__ == '__main__':
    unittest.main()
