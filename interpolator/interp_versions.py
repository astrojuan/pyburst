import numpy as np

version_defaults = {
    'param_keys': {
        'gs1826': ['accrate', 'x', 'z', 'qb', 'mass'],
        'biggrid1': ['accrate', 'x', 'z', 'qb', 'mass'],
        'biggrid2': ['accrate', 'x', 'z', 'qb', 'mass'],
    },

    'batches_exclude': {
        'gs1826': {},
        'biggrid1': {'batch': [255, 256, 257, 258, 259, 260, 471, 472, 473, 418, 419, 420]},
        'biggrid2': {},
    },

    'params_exclude': {
        'gs1826': {
                'qb': [0.5, 0.7, 0.9],
                'x': [0.6],
                'xi': [0.8, 0.9, 1.0, 1.1, 3.2],
                'z': [0.001, 0.003],
        },
        'biggrid1': {},
        'biggrid2': {
                'accrate': np.append(np.arange(5, 10) / 100, np.arange(11, 24, 2) / 100),
                'x': [0.5, 0.6, 0.8],
                'z': [0.001],
                'qb': [.075],
                'mass': [0.8, 3.2],
        },
    },
}


version_definitions = {
    'param_keys': {  # This will set the order of params when calling interpolator
        'biggrid2': {
            14: ['accrate', 'z', 'qb', 'mass'],
            15: ['accrate', 'x', 'z', 'qb', 'mass'],
            16: ['accrate', 'x', 'z', 'mass'],
        },
    },

    'batches_exclude': {
        'biggrid1': {
            1: {
                'batch': [255, 256, 257, 258, 259, 260, 471, 472, 473, 418, 419, 420]},
            },
        'biggrid2': {
            1: {},
        },
    },

    'params_exclude': {
        'gs1826': {
            1: {
                'qb': [0.5, 0.7, 0.9],
                'x': [0.6],
                'xi': [0.8, 0.9, 1.0, 1.1, 3.2],
                'z': [0.001, 0.003],
            },
        },
        'biggrid1': {
            1: {},
        },
        'biggrid2': {
            14: {
                'accrate': np.append(np.arange(5, 8) / 100, np.arange(9, 24, 2) / 100),
                'x': [0.5, 0.6, 0.8, 0.65, 0.77],
                'z': [0.001],
                'qb': [.075],
                'mass': [0.8, 3.2],
            },
            15: {
                'accrate': np.append(np.arange(5, 8) / 100, np.arange(9, 24, 2) / 100),
                'x': [0.5, 0.6, 0.8],
                'z': [0.001],
                'qb': [.075],
                'mass': [0.8, 3.2],
            },
            16: {
                'accrate': np.append(np.arange(5, 10) / 100, np.arange(11, 24, 2) / 100),
                'x': [0.5, 0.6, 0.8],
                'z': [0.001],
                'qb': [0.025, .075],
                'mass': [0.8, 3.2],
            },
        },
    },
}


class InterpVersion:
    """Class for defining different interpolator versions
    """
    def __init__(self, source, version):
        if version not in version_definitions['params_exclude'][source]:
            raise ValueError(f'version {version} of source {source} ' +
                             'is not defined in interp_versions')
        self.source = source
        self.version = version
        self.param_keys = get_param_keys(source, version)
        self.batches_exclude = get_batches_exclude(source, version)
        self.params_exclude = get_params_exclude(source, version)

    def __repr__(self):
        return (f'MCMC version definitions for {self.source} V{self.version}'
                + f'\nparam keys     : {self.param_keys}'
                + f'\nbatches exclude: {self.batches_exclude}'
                + f'\nparams_exclude : {self.params_exclude}'
                )


# ===== Convenience functions =====
def get_param_keys(source, version):
    default = version_defaults['param_keys'][source]
    return version_definitions['param_keys'][source].get(version, default)


def get_batches_exclude(source, version):
    default = version_defaults['batches_exclude'][source]
    return version_definitions['batches_exclude'][source].get(version, default)


def get_params_exclude(source, version):
    default = version_defaults['params_exclude'][source]
    return version_definitions['params_exclude'][source].get(version, default)