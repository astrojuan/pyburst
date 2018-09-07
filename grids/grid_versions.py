import numpy as np

# Defines various versions/subsets of model grids

version_defaults = {
    'exclude_any': {
        'biggrid2': {
            'accrate': np.concatenate((np.arange(5, 10)/100, np.arange(11, 24, 2)/100)),
            'qb': [0.025, 0.075, 0.125, 0.2],
            'z': [0.001, 0.0175],
            'x': [0.5, 0.6, 0.75, 0.77, 0.8],
            'mass': [0.8, 1.4, 3.2, 2.6],
        },

        'biggrid3': {},

        'grid4': {
            'accrate': [0.22],
            'mass': [2.0],
        },

        'res1': {
            'accdepth': 1e21
        },

        'heat': {'batch': [1, 8]},
    },

    'exclude_all': {
        'biggrid2': [{}],
        'biggrid3': [{}],
        'grid4': [
            {'x': 0.72, 'accdepth': 1e20},
            {'x': 0.73, 'accdepth': 1e20},
         ],

        'heat': [{}],
    },
}


version_definitions = {
    'exclude_any':
        {
            'biggrid2': {},
            'biggrid3': {},
            'grid4': {},
            'heat': {},
        },
    'exclude_all':
        {
            'biggrid2': {},
            'biggrid3': {},
            'grid4': {},
            'heat': {},
        }
}


class GridVersion:
    """Class for defining different interpolator versions
    """
    def __init__(self, source, version):
        self.source = source
        self.version = version
        self.exclude_any = get_parameter(source, version, 'exclude_any')
        self.exclude_all = get_parameter(source, version, 'exclude_all')

    def __repr__(self):
        return (f'Grid version definitions for {self.source} V{self.version}'
                + f'\nexclude_any : {self.exclude_any}'
                + f'\nexclude_all : {self.exclude_all}'
                )


def get_parameter(source, version, parameter):
    default = version_defaults[parameter][source]
    out = version_definitions[parameter][source].get(version, default)

    if out == default:
        print(f'{parameter} not defined, using default')
    if type(out) is int:
        return version_definitions[parameter][source][out]
    else:
        return out
