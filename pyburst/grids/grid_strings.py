"""
Standardised strings/labels/paths for grid models/batches/files
"""

import os

MODELS_PATH = os.environ['KEPLER_MODELS']
GRIDS_PATH = os.environ['KEPLER_GRIDS']

# TODO: rename all "gets"


def source_shorthand(source):
    """Expands source aliases (e.g. 4u ==> 4u1820)
    """
    if source == '4u':
        return '4u1820'
    elif source == 'gs':
        return 'gs1826'
    else:
        return source


def check_synth_source(source):
    """Method to check if a source is from synthetic data
    Returns reformatted string for path purposes"""
    if ('sim' in source) and (source != 'sim_test') and ('_' in source):
        idx = source.find('_')
        return source[:idx]
    else:
        return source


# ======================================================
# Basic strings
# ======================================================
def get_batch_string(batch, source, b_tag=''):
    return f'{source}_{b_tag}{batch}'


def get_run_string(run, basename='xrb', extension=''):
    return f'{basename}{run}{extension}'


def get_model_string(run, batch, source, b_tag='', r_tag=''):
    return f'{source}_{b_tag}{batch}_{r_tag}{run}'


# ======================================================
# Top level paths
# ======================================================
def top_path(sub_dir, source):
    return os.path.join(GRIDS_PATH, sub_dir, source)


def get_source_path(source):
    source = check_synth_source(source)
    return top_path(sub_dir='sources', source=source)


def get_analyser_path(source):
    source = check_synth_source(source)
    return top_path(sub_dir='analyser', source=source)


def get_obs_data_path(source):
    source = check_synth_source(source)
    return top_path(sub_dir='obs_data', source=source)


# ======================================================
# Misc. paths
# ======================================================
def get_batch_models_path(batch, source):
    batch_str = get_batch_string(batch, source)
    return os.path.join(MODELS_PATH, batch_str)


def get_model_path(run, batch, source, basename='xrb'):
    batch_path = get_batch_models_path(batch, source)
    run_str = get_run_string(run, basename=basename)
    return os.path.join(batch_path, run_str)


def batch_analysis_path(batch, source):
    batch_str = get_batch_string(batch, source)
    analysis_path = get_source_subdir(source, 'burst_analysis')
    return os.path.join(analysis_path, batch_str)


def plots_path(source):
    return get_source_subdir(source, 'plots')


def get_source_subdir(source, dir_):
    source = check_synth_source(source)
    source_path = get_source_path(source)
    return os.path.join(source_path, dir_)


# ======================================================
# Misc. files
# ======================================================
def get_batch_filename(prefix, batch, source, run=None, extension=''):
    batch_str = get_batch_string(batch, source)
    if run is not None:
        batch_str += f'_{run}'
    return f'{prefix}_{batch_str}{extension}'


def get_table_filepath(source, table, batch=None):
    """Return filepath of source (and/or batch) table (summ, params)

    Optional: provide batch, for batch-specific table
    """
    if batch is None:
        extension = '.txt'
    else:
        extension = f'_{batch}.txt'

    table_path = get_source_subdir(source, table)
    table_filename = get_source_filename(source, prefix=table, extension=extension)
    return os.path.join(table_path, table_filename)


def get_source_filename(source, prefix, extension=''):
    return f'{prefix}_{source}{extension}'


def get_model_table_filepath(batch, source, filename='MODELS.txt'):
    path = get_batch_models_path(batch, source)
    return os.path.join(path, filename)


def cmd_filepath(run, batch, source, basename='xrb'):
    path = get_model_path(run, batch, source=source, basename=basename)
    filename = get_run_string(run, basename, extension='.cmd')
    return os.path.join(path, filename)


# ======================================================
# Misc. prints
# ======================================================
def print_warning(string):
    print('X' * 70)
    print(f'WARNING: {string}')
    print('X' * 70)