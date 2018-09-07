import numpy as np
import pandas as pd
import os
from scipy.stats import linregress

# pygrids
from pygrids.grids import grid_tools, grid_analyser, grid_strings
from pygrids.kepler import kepler_tools


def extract_qnuc_table(source, ref_batch, cycles=None):
    """Extracts optimal Qnuc across parameters

    ref_batch : int
        batch that represents all unique parameters (x, z, accrate, mass)
    """
    kgrid = grid_analyser.Kgrid(source)
    ref_table = kgrid.get_params(batch=ref_batch)
    qnuc_table = iterate_solve_qnuc(source, ref_table, cycles=cycles)
    save_qnuc_table(qnuc_table, source)


def load_qnuc_table(source):
    path = grid_strings.get_source_subdir(source, 'qnuc')
    filename = grid_strings.get_source_filename(source, prefix='qnuc', extension='.txt')
    filepath = os.path.join(path, filename)
    return pd.read_table(filepath, delim_whitespace=True)


def save_qnuc_table(table, source):
    path = grid_strings.get_source_subdir(source, 'qnuc')
    filename = grid_strings.get_source_filename(source, prefix='qnuc', extension='.txt')
    filepath = os.path.join(path, filename)

    table_str = table.to_string(index=False)
    with open(filepath, 'w') as f:
        f.write(table_str)


def linregress_qnuc(source):
    """Returns table of linear fits to optimal Qnuc's (over Newtonian mass)
    """
    linr_table = pd.DataFrame()
    table = load_qnuc_table(source)
    masses = np.unique(table['mass'])
    linr_table['mass'] = masses

    for row in linr_table.itertuples():
        sub_table = grid_tools.reduce_table(table, params={'mass': row.mass})
        linr = linregress(sub_table['accrate'], sub_table['qnuc'])
        linr_table.loc[row.Index, 'm'] = linr[0]
        linr_table.loc[row.Index, 'y0'] = linr[1]
    return linr_table


def get_slopes(table, source, cycles=None, basename='xrb'):
    """Returns slopes of base temperature evolution(K/s), for given model table
    """
    slopes = []
    for row in table.itertuples():
        temps = kepler_tools.extract_base_temps(row.run, row.batch, source,
                                                cycles=cycles, basename=basename)
        i0 = 1 if len(temps) > 2 else 0  # skip first dump if possible
        linr = linregress(temps[i0:, 0], temps[i0:, 1])
        slopes += [linr[0]]

    return np.array(slopes)


def iterate_solve_qnuc(source, ref_table, cycles=None):
    """Iterates over solve_qnuc for a table of params
    """
    param_list = ['x', 'z', 'accrate', 'qb', 'accdepth', 'accmass', 'mass']
    ref_table = ref_table.reset_index()
    qnuc = np.zeros(len(ref_table))

    for row in ref_table.itertuples():
        params = {'x': row.x, 'z': row.z, 'accrate': row.accrate, 'mass': row.mass}
        qnuc[row.Index] = solve_qnuc(source=source, params=params, cycles=cycles)[0]

    qnuc_table = ref_table.copy()[param_list]
    qnuc_table['qnuc'] = qnuc
    return qnuc_table


def solve_qnuc(source, params, cycles=None):
    """Returns predicted Qnuc that gives zero slope in base temperature
    """
    param_list = ('x', 'z', 'accrate', 'mass')
    for p in param_list:
        if p not in params:
            raise ValueError(f'Missing "{p}" from "params"')

    kgrid = grid_analyser.Kgrid(source)
    subset = kgrid.get_params(params=params)
    slopes = get_slopes(table=subset, source=source, cycles=cycles)

    linr = linregress(subset['qnuc'], slopes)
    x0 = -linr[1]/linr[0]  # x0 = -y0/m
    u_x0 = (linr[4] / linr[0]) * x0
    return x0, u_x0