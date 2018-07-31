"""
Wrapper for sequential burst analysis routines, such as:
    - copying params table files
    - loading/saving lightcurve files
    - analysing models
    - collecting the results
"""
import numpy as np
import pandas as pd
import multiprocessing as mp
import os
import sys
import time

# kepler_grids
from . import burst_analyser
from . import burst_tools
from ..grids import grid_tools, grid_strings
from ..misc.pyprint import printv, print_title

GRIDS_PATH = os.environ['KEPLER_GRIDS']
MODELS_PATH = os.environ['KEPLER_MODELS']


def run_analysis(batches, source, copy_params=True, reload=True, multithread=True,
                 analyse=True, collect=True, verbose=True):
    """Run sequential analysis steps for burst models
    """
    # TODO: multithread by runs (for large batches)

    # 1.
    if copy_params:
        print_title('Copying parameter tables')
        grid_tools.copy_paramfiles(batches, source)
        # TODO combine paramfiles (grid_tools)

    # 2.
    if reload:
        print_title('Loading lightcurve files')
        burst_tools.multi_batch_save(batches, source, multithread=multithread)

    # 3.
    if analyse:
        print_title('Extracting burst properties from models')
        if multithread:
            multithread_extract(batches, source)
        else:
            extract_bursts(batches, source)

    # 4.
    if collect:
        print_title('Collecting results')
        last_batch = batches[-1]
        burst_tools.combine_extracts(np.arange(1, last_batch + 1), source)


def multithread_extract(batches, source, plot_model=True, plot_convergence=True,
                        plot_linregress=True):
    args = []
    for batch in batches:
        args.append([batch, source, plot_model, plot_convergence, plot_linregress])

    t0 = time.time()
    with mp.Pool(processes=8) as pool:
        pool.starmap(extract_bursts, args)
    t1 = time.time()
    dt = t1 - t0
    print(f'Time taken: {dt:.1f} s ({dt/60:.2f} min)')


def extract_bursts(batches, source, plot_model=True, plot_convergence=True,
                   plot_linregress=True):
    source_path = grid_strings.get_source_path(source)
    batches = grid_tools.expand_batches(batches, source)
    bool_map = {True: 'Y', False: 'N'}

    flags = ('converged',)
    b_ints = ('batch', 'run', 'num', 'discard')
    bprops = ('dt', 'fluence', 'length', 'peak')
    col_order = ['batch', 'run', 'num', 'converged', 'discard', 'dt', 'u_dt', 'rate', 'u_rate',
                 'fluence', 'u_fluence', 'length', 'u_length', 'peak', 'u_peak']

    for batch in batches:
        batch_str = f'{source}_{batch}'
        analysis_path = os.path.join(source_path, 'burst_analysis', batch_str)
        grid_tools.try_mkdir(analysis_path, skip=True)

        filename = f'burst_analysis_{batch_str}.txt'
        filepath = os.path.join(analysis_path, filename)

        data = {}
        for bp in bprops:
            u_bp = f'u_{bp}'
            data[bp] = []
            data[u_bp] = []

        data['rate'] = []
        data['u_rate'] = []

        for b in (b_ints + flags):
            data[b] = []

        n_runs = grid_tools.get_nruns(batch, source)
        for run in range(1, n_runs + 1):
            sys.stdout.write(f'\r{source}_{batch} xrb{run:02}')
            burstfit = burst_analyser.BurstRun(run, batch, source,
                                               analyse=True)
            data['batch'] += [batch]
            data['run'] += [run]
            data['num'] += [burstfit.n_bursts]
            data['discard'] += [burstfit.discard]
            data['converged'] += [bool_map[burstfit.converged]]

            for bp in bprops:
                u_bp = f'u_{bp}'
                data[bp] += [burstfit.summary[f'mean_{bp}']]
                data[u_bp] += [burstfit.summary[f'std_{bp}']]

            data['rate'] += [8.64e4 / data['dt'][-1]]  # burst rate (per day)
            data['u_rate'] += [8.64e4 * data['u_dt'][-1] / data['dt'][-1] ** 2]

            if not burstfit.too_few_bursts:
                if plot_model:
                    burstfit.plot_model(display=False, save=True)
                if plot_convergence:
                    burstfit.plot_convergence(display=False, save=True)

                if plot_linregress and not burstfit.regress_too_few_bursts:
                    burstfit.plot_linregress(display=False, save=True)

        table = pd.DataFrame(data)
        table = table[col_order]
        table_str = table.to_string(index=False, justify='left', col_space=12,
                                    formatters={'discard': '{:.0f}'.format})

        with open(filepath, 'w') as f:
            f.write(table_str)


def check_n_bursts(batches, source, kgrid):
    """Compares n_bursts detected with kepler_analyser against burstfit_1808
    """
    mismatch = np.zeros(4)
    filename = f'mismatch_{source}_{batches[0]}-{batches[-1]}.txt'
    filepath = os.path.join(GRIDS_PATH, filename)

    for batch in batches:
        summ = kgrid.get_summ(batch)
        n_runs = len(summ)

        for i in range(n_runs):
            run = i + 1
            n_bursts1 = summ.iloc[i]['num']
            sys.stdout.write(f'\r{source}_{batch} xrb{run:02}')

            burstfit = burst_analyser.BurstRun(run, batch, source, verbose=False)
            burstfit.analyse()
            n_bursts2 = burstfit.n_bursts

            if n_bursts1 != n_bursts2:
                m_new = np.array((batch, run, n_bursts1, n_bursts2))
                mismatch = np.vstack((mismatch, m_new))

        np.savetxt(filepath, mismatch)
    return mismatch
