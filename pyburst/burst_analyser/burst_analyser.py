import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

from scipy import interpolate, integrate
from scipy.signal import argrelextrema
from scipy.stats import linregress

# kepler_grids
from pyburst.burst_analyser import burst_tools
from pyburst.grids import grid_tools, grid_strings
from pyburst.kepler import kepler_tools
from pyburst.kepler import kepler_plot
from pyburst.physics import accretion

GRIDS_PATH = os.environ['KEPLER_GRIDS']
MODELS_PATH = os.environ['KEPLER_MODELS']

plt.rc('text', usetex=False)
plt.rc('font', family='serif')


# TODO: Generalise to non-batch organised models
# TODO: param description docstring


class NoBursts(Exception):
    pass

class NoDumps(Exception):
    pass


class BurstRun(object):
    def __init__(self, run, batch, source, verbose=True, basename='xrb',
                 reload=False, save_lum=True, analyse=True, plot=False,
                 exclude_outliers=True, exclude_short_wait=True, load_lum=True,
                 load_bursts=False, load_summary=False, try_mkdir_plots=False,
                 load_dumps=False, set_paramaters=None, auto_discard=False,
                 get_slopes=False, load_model_params=True, truncate_edd=False,
                 check_stable_burning=True, quick_discard=True,
                 check_lumfile_monotonic=True):
        self.flags = {'lum_loaded': False,
                      'lum_does_not_exist': False,
                      'dumps_loaded': False,
                      'analysed': False,
                      'too_few_bursts': False,
                      'short_waits': False,
                      'outliers': False,
                      'regress_too_few_bursts': False,
                      'converged': False,
                      'shocks': False,
                      'zeros': False,
                      'calculated_slopes': False,
                      'super_eddington': False,
                      'stable_burning': False,
                      }

        self.options = {'verbose': verbose,
                        'reload': reload,
                        'save_lum': save_lum,
                        'exclude_outliers': exclude_outliers,
                        'exclude_short_wait': exclude_short_wait,
                        'try_mkdir_plots': try_mkdir_plots,
                        'auto_discard': auto_discard,
                        'get_slopes': get_slopes,
                        'load_model_params': load_model_params,
                        'truncate_edd': truncate_edd,
                        'check_stable_burning': check_stable_burning,
                        'quick_discard': quick_discard,
                        'check_lumfile_monotonic': check_lumfile_monotonic,
                        }
        self.check_options()

        self.parameters = {'lum_cutoff': 1e36,  # luminosity cutoff for burst detection
                           'shock_radius': 2,  # neighbour zones to compare for shocks
                           'shock_frac': 2.0,  # lum factor that shocks exceed neighbours by
                           'zero_replacement': 1e35,  # zero lums set to this
                           'maxima_radius': 60,  # bursts are largest maxima within (sec)
                           'pre_time': 60,  # look for burst rise within sec before peak
                           'start_frac': 0.25,  # burst start as frac of peak lum above lum_pre
                           'peak_frac': 2,  # peak must be larger than pre_lum by this frac
                           'end_frac': 0.01,  # burst end lum is this frac of peak lum
                           'min_length': 5,  # min time between burst peak and end (sec)
                           'short_wait_frac': 0.5,  # short_waits below frac of following dt
                           'min_discard': 2,  # min num of bursts to discard
                           'ideal_discard': 10,  # no. bursts to attempt to discard, but fall back on min_discard
                           'min_bursts': 10,  # min no. bursts (after discards) to calculate mean properties
                           'min_regress': 20,  # min num of bursts to do linear regression
                           'n_bimodal': 20,  # n_bursts to check for bimodality
                           'bimodal_sigma': 3,  # number of std's modes are separated by
                           'outlier_bprops': ('dt', 'fluence', 'peak'),  # bprops to check
                           'outlier_distance': 3.,  # fraction of IQR above Q3
                           'max_shock_iterations': 100,  # max cycles in get_burst_candidates()
                           'dump_time_offset': 0.0,  # time offset (s) from burst start
                           'dump_time_min': 1,  # min time (s) between t_start and dump time
                           'min_rise_steps': 5,  # min time steps between t_pre and t_peak
                           'stable_dt_frac': 10,  # no. of dt's from last burst to end of model to flag stable burning
                           }
        self.overwrite_parameters(set_paramaters)

        self.colours = {'bursts': 'C1',
                        'candidates': 'C3',
                        'outliers': 'C9',
                        'short_waits': 'C4',
                        'burst_stages': 'C2',
                        'shocks': 'C3',
                        'dumps': 'C0',
                        }

        self.cols = ['n', 'dt', 'rate', 'fluence', 'peak', 'length', 't_peak', 't_peak_i',
                     't_pre', 't_pre_i', 'lum_pre', 't_start', 't_start_i',
                     'lum_start', 't_end', 't_end_i', 'lum_end', 'slope_dt',
                     'slope_dt_err', 'slope_fluence', 'slope_fluence_err',
                     'slope_peak', 'slope_peak_err', 'short_wait', 'outlier',
                     'dump_start']

        self.paths = {'batch_models': grid_strings.get_batch_models_path(batch, source),
                      'source': grid_strings.get_source_path(source),
                      'analysis': grid_strings.batch_analysis_path(batch, source),
                      'plots': grid_strings.get_source_subdir(source, 'plots'),
                      }

        self.run = run
        self.batch = batch
        self.source = source
        self.basename = basename
        self.run_str = grid_strings.get_run_string(run, basename)
        self.batch_str = grid_strings.get_batch_string(batch, source)
        self.model_str = grid_strings.get_model_string(run, batch, source)

        self.lum = None
        self.lumf = None
        self.new_lum = None
        self.l_edd = None
        self.model_params = None
        self.load_bursts = load_bursts
        self.load_summary = load_summary
        self.load_dumps = load_dumps
        self.bursts = pd.DataFrame(columns=self.cols)
        self.n_bursts = None
        self.n_short_wait = None
        self.n_outliers = None
        self.n_outliers_unique = None

        self.summary = {}
        self.candidates = None
        self.bprops = ['dt', 'fluence', 'peak', 'length']
        self.shocks = []
        self.dumpfiles = None
        self.dump_table = None

        # ====== linregress things ======
        self.regress_bprops = ['dt', 'fluence', 'peak']
        self.discard = None

        # ====== Loading things ======
        if self.options['load_model_params']:
            self.load_model_params()

        if load_lum:
            self.load_lum_file()

        if self.load_bursts:
            self.load_burst_table()

        if self.load_dumps:
            self.load_dumpfiles()

        if self.load_summary:
            if not self.load_bursts:
                self.print_warn('Loading summary but not bursts. The summary values are '
                                + 'not gauranteed to match the burst properties.'
                                + '\nTHIS IS NOT RECOMMENDED')
            self.load_summary_table()

        if truncate_edd:
            self.l_edd = accretion.eddington_lum(mass=self.model_params['mass'], x=0.0)

        if analyse:
            self.analyse()
        if plot:
            self.plot()

    # ===========================================================
    # Loading/setup
    # ===========================================================
    def check_options(self):
        """Checks consistency of selected options
        """
        if self.options['quick_discard'] and self.options['auto_discard']:
            raise ValueError('Only one of (quick_discard, auto_discard) can be activated')

    def load_model_params(self):
        """Load model parameters from grid table
        """
        try:
            batch_table = grid_tools.load_model_table(self.batch, source=self.source)
        except FileNotFoundError:
            try:
                grid_table = grid_tools.load_grid_table('params', source=self.source)
                batch_table = grid_tools.reduce_table(grid_table,
                                                      params={'batch': self.batch})
            except FileNotFoundError:
                self.print_warn('Model parameter table not found. '
                                'Has the source grid been analysed yet?')
                return

        model_row = grid_tools.reduce_table(batch_table, params={'run': self.run})
        params_dict = model_row.to_dict(orient='list')

        for key, value in params_dict.items():
            params_dict[key] = value[0]

        self.model_params = params_dict

    def check_lum_loaded(self):
        """Checks if luminosity file has been loaded
        """
        if not self.flags['lum_loaded']:
            if self.flags['lum_does_not_exist']:
                return
            else:
                self.load_lum_file()

    def load_lum_file(self):
        """Load luminosity data from kepler simulation
        """
        self.lum = burst_tools.load_lum(run=self.run, batch=self.batch,
                                        source=self.source, basename=self.basename,
                                        save=self.options['save_lum'],
                                        reload=self.options['reload'],
                                        check_monotonic=self.options['check_lumfile_monotonic'])

        if self.lum is None:
            self.flags['lum_does_not_exist'] = True
            self.n_bursts = 0
            return

        self.lumf = interpolate.interp1d(self.lum[:, 0], self.lum[:, 1])
        self.flags['lum_loaded'] = True

    def overwrite_parameters(self, set_parameters):
        """Overwrite default analysis parameters
        """
        if set_parameters is not None:
            if type(set_parameters) is dict:
                for param, value in set_parameters.items():
                    self.printv(f'Overwriting default analysis parameter: {param}={value}')
                    if param in self.parameters:
                        self.parameters[param] = value
                    else:
                        raise ValueError(f"parameter '{param}' not in self.parameters")
            else:
                raise TypeError("'set_parameters' must be type dict")

    def load_burst_table(self):
        """Load pre-extracted burst properties from file
        """
        self.printv('Loading pre-extracted bursts from file')
        self.bursts = burst_tools.load_run_table(run=self.run, batch=self.batch,
                                                 source=self.source, table='bursts')
        self.n_bursts = len(self.bursts)
        self.n_short_wait = len(self.short_waits())
        self.n_outliers = len(self.outliers())
        self.n_outliers_unique = len(self.outliers(unique=True))

        self.determine_flags_from_table()

    def determine_flags_from_table(self):
        """Determine flags from a loaded burst table (without full analysis)
        """
        if self.n_short_wait > 0:
            self.flags['short_waits'] = True

        if self.n_outliers_unique > 0:
            self.flags['outliers'] = True

        if self.n_bursts < 2:
            self.flags['too_few_bursts'] = True

        if False not in np.isnan(np.array(self.bursts['slope_dt'])):
            self.flags['regress_too_few_bursts'] = True

    def load_summary_table(self):
        self.printv('Loading pre-extracted model summary from file')
        summary_table = burst_tools.load_run_table(run=self.run, batch=self.batch,
                                                   source=self.source, table='summary')

        self.summary = summary_table.to_dict('list')
        for key, val in self.summary.items():
            self.summary[key] = val[0]  # don't store as arrays

    def load_dumpfiles(self):
        """Load available kepler dumpfiles
        """
        # TODO: what happens if there are no dumpfiles?
        self.dumpfiles = kepler_tools.load_dumps(self.run, batch=self.batch,
                                                 source=self.source,
                                                 basename=self.basename)

        self.dump_table = kepler_tools.extract_dump_table(self.run, batch=self.batch,
                                                          source=self.source,
                                                          basename=self.basename,
                                                          dumps=self.dumpfiles)
        self.flags['dumps_loaded'] = True

    def check_dumpfiles(self):
        """Checks if dumpfiles are loaded, and whether they need to be
        """
        if not self.flags['dumps_loaded']:
            if self.load_dumps:
                self.load_dumpfiles()
            else:
                self.printv('Dumpfiles not loaded')
                raise NoDumps

    def setup_summary(self):
        """Collects remaining model properties into dictionary
        """
        self.summary['batch'] = self.batch
        self.summary['run'] = self.run
        self.summary['num'] = self.n_bursts
        self.summary['burn_in'] = self.discard
        self.summary['converged'] = self.flags['converged']
        self.summary['short_waits'] = self.flags['short_waits']
        self.summary['outliers'] = self.flags['outliers']
        self.summary['n_outliers'] = self.n_outliers_unique
        self.summary['n_short_waits'] = self.n_short_wait
        self.get_means()
        self.test_bimodal()

    # ===========================================================
    # Accessing data
    # ===========================================================
    def printv(self, string):
        if self.options['verbose']:
            print(string)

    def print_warn(self, string):
        full_string = f"\nWARNING: {string}\n"
        self.printv(full_string)

    def print_summary(self):
        """Print summary of burst properties
        """
        self.ensure_analysed_is(True)
        for bprop in self.bprops:
            value = self.summary[bprop]
            u_value = self.summary[f'u_{bprop}']

            power = int(np.log10(value))
            print(f'{bprop} = {value*10**(-power):.4f} +/- {u_value*10**(-power):.4f} '
                  f'(10^{power})')

    def save_summary_table(self):
        """Saves table of model summary to file
        """
        self.ensure_analysed_is(True)
        table = pd.DataFrame()
        for col in self.summary:
            table[col] = [self.summary[col]]

        filename = f'summary_{self.model_str}.txt'
        filepath = os.path.join(self.paths['analysis'], 'output', filename)
        table_str = table.to_string(index=False, justify='left')
        with open(filepath, 'w') as f:
            f.write(table_str)

    def save_burst_table(self):
        """Saves table of burst properties to file
        """
        self.ensure_analysed_is(True)
        filename = f'bursts_{self.model_str}.txt'
        filepath = os.path.join(self.paths['analysis'], 'output', filename)

        table = self.bursts[self.cols]
        table_str = table.to_string(index=False, justify='left')

        with open(filepath, 'w') as f:
            f.write(table_str)

    def ensure_analysed_is(self, analysed):
        """Checks that model has (or hasn't) been analysed
        """
        strings = {True: 'Model not yet analysed. Run self.analyse() first',
                   False: 'Model has already been analysed. Reload model first'}

        if self.flags['analysed'] != analysed:
            if self.flags['too_few_bursts']:
                string = 'Too few bursts for analysis'
            else:
                string = strings[analysed]
            raise AttributeError(string)

    def clean_bursts(self, exclude_short_wait=None, exclude_outliers=None,
                     exclude_min_regress=False, exclude_discard=False):
        """Returns subset of self.bursts that are not in min_discard,
            and (depending on exclude options), not outliers or short_waits

        parameters
        ----------
        exclude_short_wait : bool (optional)
            if not provided, fall back on self.options
        exclude_outliers : bool (optional)
            if not provided, fall back on self.options
        exclude_min_regress : bool (optional)
        exclude_discard : bool (optional)
        """
        # Fall back on default options
        if exclude_short_wait is None:
            exclude_short_wait = self.options['exclude_short_wait']
        if exclude_outliers is None:
            exclude_outliers = self.options['exclude_outliers']

        mask = np.full(self.n_bursts, True)
        mask[:self.parameters['min_discard']] = False

        if exclude_short_wait:
            mask = mask & np.invert(self.bursts['short_wait'])
        if exclude_outliers:
            mask = mask & np.invert(self.bursts['outlier'])
        if exclude_discard:
            mask[:self.discard] = False

        if exclude_min_regress:
            return self.bursts[mask].iloc[:-self.parameters['min_regress'] + 1]
        else:
            return self.bursts[mask]

    def short_waits(self):
        """Returns subset of self.bursts that are classified as short_wait
        """
        mask = self.bursts['short_wait']
        return self.bursts[mask]

    def not_short_waits(self):
        """Returns subset of self.bursts that are NOT classified as short_wait
        """
        mask = np.invert(self.bursts['short_wait'])
        return self.bursts[mask]

    def outliers(self, unique=False):
        """Returns subset of self.bursts that are outliers

        unique : bool
            whether to exclude bursts already identified as short_waits or min_discard
        """
        if unique:
            mask = self.bursts['outlier'] & np.invert(self.bursts['short_wait'])
            mask.iloc[:self.parameters['min_discard']] = False
        else:
            mask = self.bursts['outlier']

        return self.bursts[mask]

    def not_outliers(self):
        return self.bursts[np.invert(self.bursts['outlier'])]

    def dumps_starts(self):
        """Returns subset of dump_table identified as bursts.dump_starts
        """
        try:
            self.check_dumpfiles()
        except NoDumps:
            return

        mask = ~np.isnan(self.bursts['dump_start'])
        cycles = self.bursts['dump_start'][mask].astype(int)
        table = self.dump_table.set_index('cycle')
        return table.loc[cycles]

    # ===========================================================
    # Analysis
    # ===========================================================
    def analyse(self):
        """Performs complete analysis of model.
        """
        self.ensure_analysed_is(False)
        if not self.load_bursts:
            self.identify_bursts()

            if self.options['truncate_edd']:
                self.truncate_eddington()

            self.get_fluences()
            self.identify_outliers()

            if self.options['get_slopes']:
                self.get_bprop_slopes()

            self.get_burst_dumps()
        elif self.options['truncate_edd']:
            self.truncate_eddington()

        if self.options['quick_discard']:
            self.discard = self.quick_discard()
        elif self.options['auto_discard']:
            self.discard = self.get_auto_discard()
        else:
            self.printv("Discarding default initial bursts, "
                        f"min_discard={self.parameters['min_discard']}")
            self.discard = self.parameters['min_discard']

        if not self.load_summary:
            self.setup_summary()

        if self.options['check_stable_burning']:
            self.check_stable_burning()

        self.flags['analysed'] = True

    def identify_bursts(self):
        """Extracts peaks, times, and recurrence times of bursts

         Pipeline:
         ---------
           1. Get maxima above minimum threshold
           2. Discard shock peaks
           3. Get largest peaks in some radius
           4. Identify short-wait bursts (below some fraction of mean dt)
           5. Get start/end times (discard final burst if cut off)
        """
        self.printv('Identifying bursts')
        self.check_lum_loaded()
        self.get_burst_candidates()

        try:
            self.get_burst_peaks()
        except NoBursts:
            return

        self.get_burst_starts()
        self.get_burst_ends()
        self.get_recurrence_times()
        self.get_burst_rates()

        try:
            self.check_n_bursts()
        except NoBursts:
            return

        self.identify_short_wait_bursts()
        self.bursts.reset_index(inplace=True, drop=True)

        self.bursts['length'] = self.bursts['t_end'] - self.bursts['t_start']
        self.bursts['n'] = np.arange(self.n_bursts) + 1  # burst ID (starting from 1)

    def get_burst_candidates(self):
        """Identify potential bursts, while removing shocks in lightcurve
        """
        old_candidates = [0]
        candidates = self.get_lum_maxima()
        count = 0

        while not np.array_equal(old_candidates, candidates):
            old_candidates = candidates
            self.remove_shocks(candidates)
            candidates = self.get_lum_maxima()

            count += 1
            if count == self.parameters['max_shock_iterations']:
                self.print_warn('Reached maximum iterations of shock-removal, '
                                + 'lightcurve should be verified')
                break

        print(f'Shock removal iterations: {count}')
        self.candidates = candidates
        self.shocks = np.array(self.shocks)

    def truncate_eddington(self):
        """Truncates all super-Eddington luminosities from model lightcurve
        """
        mask = self.lum[:, 1] > self.l_edd
        if True in mask:
            self.printv('Truncating super-Eddington luminosities')
            self.flags['super_eddington'] = True
            self.lum[:, 1][mask] = self.l_edd

            # ----- reset burst peaks -----
            peak_mask = self.bursts['peak'] > self.l_edd
            self.bursts.loc[peak_mask, 'peak'] = self.l_edd

        self.lumf = interpolate.interp1d(self.lum[:, 0], self.lum[:, 1])

    def get_lum_maxima(self):
        """Returns all maxima in luminosity above lum_thresh
        """
        radius = self.parameters['shock_radius']
        lum = self.lum[radius:-radius]

        thresh_i = np.where(lum[:, 1] > self.parameters['lum_cutoff'])[0]
        lum_cut = lum[thresh_i]

        maxima_i = argrelextrema(lum_cut[:, 1], np.greater)[0]
        return lum_cut[maxima_i]

    def remove_shocks(self, maxima):
        """Cut out convective shocks (extreme spikes in luminosity).
        Identifies spikes, and replaces them with interpolation from neighbours.

        parameters
        ----------
        maxima : nparray(n,2)
            local maxima to check (t, lum)
        """
        self.remove_zeros()
        radius = self.parameters['shock_radius']
        # ----- Discard if maxima more than [tolerance] larger than all neighbours -----
        for max_i in maxima:
            t, lum = max_i
            idx = np.searchsorted(self.lum[:, 0], t)

            left = self.lum[idx - radius: idx, 1]  # left neighbours
            right = self.lum[idx + 1: idx + radius + 1, 1]  # right neighbours
            neighbours = np.concatenate([left, right])

            if True in (lum > self.parameters['shock_frac'] * neighbours):
                if not self.flags['shocks']:
                    self.printv('Shocks detected and removed: consider verifying'
                                ' with self.plot(shocks=True)')
                    self.flags['shocks'] = True

                new_lum = 0.5 * (left[-1] + right[0])  # mean of two neighbours
                max_i[1] = new_lum
                self.lum[idx, 1] = new_lum
                self.shocks.append([idx, t, lum])

    def remove_zeros(self):
        """During shocks, kepler can also give zero luminosity (for some reason...)
        """
        zeros = np.where(self.lum[:, 1] == 0.0)
        if len(zeros) > 0:
            if not self.flags['zeros']:
                self.printv(f'Zeros removed from luminosity')
                self.flags['zeros'] = True
            self.lum[zeros, 1] = self.parameters['zero_replacement']

    def get_burst_peaks(self):
        """Keep largest maxima within some time-window
        """
        t_radius = self.parameters['maxima_radius']
        peaks = []

        for maxi in self.candidates:
            t, lum = maxi
            i_left = np.searchsorted(self.lum[:, 0], t - t_radius)
            i_right = np.searchsorted(self.lum[:, 0], t + t_radius)

            maxx = np.max(self.lum[i_left:i_right, 1])
            if maxx == lum:
                peaks.append(maxi)

        peaks = np.array(peaks)
        self.n_bursts = len(peaks)
        self.check_n_bursts()
        self.bursts['t_peak'] = peaks[:, 0]  # times of burst peaks (s)
        self.bursts['t_peak_i'] = np.searchsorted(self.lum[:, 0], self.bursts['t_peak'])
        self.bursts['peak'] = peaks[:, 1]  # Peak luminosities (erg/s)

    def check_n_bursts(self):
        if self.flags['too_few_bursts'] or self.flags['regress_too_few_bursts']:
            pass
        elif self.n_bursts < 2:
            self.flags['too_few_bursts'] = True
            self.flags['regress_too_few_bursts'] = True
            message = {0: 'No bursts in this model',
                       1: 'Only one burst detected'}[self.n_bursts]
            self.print_warn(message)

            if self.n_bursts == 0:
                raise NoBursts
        elif (self.n_bursts - self.parameters['min_discard']) < 1:
            self.print_warn('n_bursts < min_discard, most analysis will be skipped')
            self.flags['too_few_bursts'] = True
            self.flags['regress_too_few_bursts'] = True

    def get_recurrence_times(self):
        """Finds recurence times (dt (s), time between bursts)
        """
        if self.n_bursts > 1:
            dt = np.diff(self.bursts['t_peak'])
            self.bursts['dt'] = np.concatenate(([np.nan], dt))  # Recurrence times (s)
        elif self.n_bursts == 1:
            self.bursts['dt'] = np.nan

    def get_burst_rates(self):
        """Calculates burst rates (per day)
        """
        if self.n_bursts > 1:
            self.bursts['rate'] = (24*3600) / self.bursts['dt']
        elif self.n_bursts == 1:
            self.bursts['rate'] = np.nan

    def get_burst_starts(self):
        """Finds first point in lightcurve that reaches a given fraction of the peak
        """
        self.bursts['t_pre'] = self.bursts['t_peak'] - self.parameters['pre_time']
        self.bursts['t_pre_i'] = np.searchsorted(self.lum[:, 0], self.bursts['t_pre'])
        self.bursts['lum_pre'] = self.lum[self.bursts['t_pre_i'], 1]

        self.bursts['t_start'] = np.full(self.n_bursts, np.nan)
        self.bursts['t_start_i'] = np.zeros(self.n_bursts, dtype=int)

        for burst in self.bursts.itertuples():
            rise_steps = burst.t_peak_i - burst.t_pre_i
            if rise_steps < self.parameters['min_rise_steps'] \
                    or (burst.peak / burst.lum_pre) < self.parameters['peak_frac']:
                self.printv(f'Excluding micro-burst at t={burst.t_peak:.0f} s '
                            + f'({burst.t_peak/3600:.1f} hr)')
                try:
                    self.delete_burst(burst.Index)
                except NoBursts:
                    self.bursts['lum_start'] = np.nan
                    return
                continue

            lum_slice = self.lum[burst.t_pre_i:burst.t_peak_i]
            pre_lum = lum_slice[0, 1]
            peak_lum = lum_slice[-1, 1]
            start_lum = pre_lum + self.parameters['start_frac'] * (peak_lum - pre_lum)

            slice_i = np.searchsorted(lum_slice[:, 1], start_lum)
            t_start = lum_slice[slice_i, 0]
            self.bursts.loc[burst.Index, 't_start'] = t_start
            self.bursts.loc[burst.Index, 't_start_i'] = np.searchsorted(self.lum[:, 0], t_start)

        self.bursts['lum_start'] = self.lum[self.bursts['t_start_i'], 1]

    def get_burst_ends(self):
        """Finds first point in lightcurve > min_length after peak that falls
        to a given fraction of luminosity
        """
        self.bursts['t_end'] = np.full(self.n_bursts, np.nan)
        self.bursts['t_end_i'] = np.zeros(self.n_bursts, dtype=int)

        for burst in self.bursts.itertuples():
            lum_slice = self.lum[burst.t_peak_i:]
            pre_lum = self.lum[burst.t_pre_i, 1]

            peak_t, peak_lum = lum_slice[0]
            lum_diff = peak_lum - pre_lum

            time_from_peak = lum_slice[:, 0] - peak_t
            threshold_lum = pre_lum + (self.parameters['end_frac'] * lum_diff)
            thresh_i = np.where(lum_slice[:, 1] < threshold_lum)[0]

            min_length_i = np.where(time_from_peak > self.parameters['min_length'])[0]
            intersection = list(set(thresh_i).intersection(min_length_i))

            if len(intersection) == 0:
                if burst.Index == self.bursts.index[-1]:
                    self.printv('File ends during burst. Discarding final burst')
                    try:
                        self.delete_burst(burst.Index)
                    except NoBursts:
                        self.bursts['lum_end'] = np.nan
                        return
                    continue
                else:
                    raise RuntimeError(f'Failed to find end of burst {burst.Index + 1}, '
                                       + f't={peak_t:.0f} s ({peak_t/3600:.1f} hr)')
            else:
                end_i = np.min(intersection)
                t_end = lum_slice[end_i, 0]
                self.bursts.loc[burst.Index, 't_end'] = t_end
                self.bursts.loc[burst.Index, 't_end_i'] = np.searchsorted(self.lum[:, 0], t_end)

        self.bursts['lum_end'] = self.lum[self.bursts['t_end_i'], 1]

    def delete_burst(self, burst_i):
        """Removes burst from self.bursts table
        """
        self.bursts = self.bursts.drop(burst_i)
        self.n_bursts -= 1

        if self.n_bursts == 0:  # have deleted last burst
            self.print_warn('Discarded only burst')
            raise NoBursts
        # TODO: this won't catch if the second burst is also deleted after the first
        if burst_i == 0:    # if deleting first burst, second burst has undefined dt
            self.bursts.loc[1, 'dt'] = np.nan

    def identify_short_wait_bursts(self):
        """Identify bursts which have unusually short recurrence times
            Here defined as less than 'min_dt_frac' of the following burst
        """
        self.bursts['short_wait'] = np.full(self.n_bursts, False)
        if self.n_bursts < 3:
            self.printv('Too few bursts to identify short-waits')
            self.n_short_wait = 0
            return

        dt_0 = np.array(self.bursts.iloc[1:-1]['dt'])
        dt_1 = np.array(self.bursts.iloc[2:]['dt'])
        short_wait = dt_0 < (self.parameters['short_wait_frac'] * dt_1)

        self.bursts.loc[self.bursts.index[1]:self.bursts.index[-2], 'short_wait'] = short_wait
        self.n_short_wait = len(self.short_waits())

        if self.n_short_wait > 0:
            self.printv(f'{self.n_short_wait} short-wait bursts detected')
            self.flags['short_waits'] = True

    def get_fluences(self):
        """Calculates burst fluences by integrating over burst luminosity
        """
        self.bursts['fluence'] = np.zeros(self.n_bursts)
        for burst in self.bursts.itertuples():
            lum_slice = self.lum[burst.t_pre_i:burst.t_end_i]
            self.bursts.loc[burst.Index, 'fluence'] = integrate.trapz(y=lum_slice[:, 1],
                                                                      x=lum_slice[:, 0])

    def identify_outliers(self):
        """Identify outlier bursts

        Note: bursts up to min_discard and short_waits will not be included
                in the calculation of the mean
        """
        def too_few():
            self.printv('Too few bursts to get outliers')
            self.n_outliers = 0
            self.n_outliers_unique = 0

        self.bursts['outlier'] = np.full(self.n_bursts, False)

        if self.flags['too_few_bursts']:
            too_few()
            return

        outliers = self.bursts.copy()['outlier']

        for bprop in self.parameters['outlier_bprops']:
            clean = self.clean_bursts(exclude_outliers=False)[bprop]

            if len(clean) == 0:
                too_few()
                return

            percentiles = burst_tools.get_quartiles(clean, self.parameters['outlier_distance'])

            outliers = ((self.bursts[bprop] < percentiles[0])
                        | (self.bursts[bprop] > percentiles[-1])
                        | outliers)
            outliers[:self.parameters['min_discard']] = True  # min_discard always outliers

        self.bursts['outlier'] = outliers
        self.n_outliers = len(self.outliers())
        self.n_outliers_unique = len(self.outliers(unique=True))

        if self.n_outliers_unique > 0:
            self.printv(f'{self.n_outliers_unique} additional outliers identified')
            self.flags['outliers'] = True

    def get_bprop_slopes(self):
        """Calculate slopes for properties as the burst sequence progresses
        """
        def too_few():
            self.flags['regress_too_few_bursts'] = True
            minimum = (self.parameters['min_regress'] + self.parameters['min_discard']
                       + self.n_short_wait + self.n_outliers_unique)
            self.printv(f'Too few bursts to get slopes. '
                        + f'Has {self.n_bursts}, need at least {minimum} '
                        + '(assuming no further outliers/short_waits occur)')

        try:
            self.printv('Calculating slopes in burst properties (along burst train)')
            for bprop in self.regress_bprops:
                self.bursts[f'slope_{bprop}'] = np.full(self.n_bursts, np.nan)
                self.bursts[f'slope_{bprop}_err'] = np.full(self.n_bursts, np.nan)

            if self.flags['regress_too_few_bursts']:
                too_few()
                return

            bursts_regress = self.clean_bursts(exclude_min_regress=True)
            bursts_regress_full = self.clean_bursts(exclude_min_regress=False)

            if len(bursts_regress) > 0:
                for bprop in self.regress_bprops:
                    for burst in bursts_regress.itertuples():
                        regress_slice = bursts_regress_full[burst.Index:]
                        lin = linregress(regress_slice['n'], regress_slice[bprop])

                        self.bursts.loc[burst.Index, f'slope_{bprop}'] = lin[0]
                        self.bursts.loc[burst.Index, f'slope_{bprop}_err'] = lin[-1]
            else:
                too_few()
        finally:
            self.flags['calculated_slopes'] = True

    def quick_discard(self):
        """Returns no. of bursts to discard based on simple criteria
        """
        self.printv('Finding quick number of bursts to discard')

        ideal_discard = self.parameters['ideal_discard']
        min_discard = self.parameters['min_discard']
        too_few_str = f'Too few bursts for ideal_discard, using min_discard={min_discard}'

        if self.flags['too_few_bursts']:
            self.printv(too_few_str)
            return min_discard

        n_remaining = self.n_bursts - ideal_discard

        if n_remaining < self.parameters['min_bursts']:
            self.printv(too_few_str)
            return min_discard
        else:
            self.printv(f"Using ideal_discard={ideal_discard}")
            return ideal_discard

    def get_auto_discard(self):
        """Returns min no. of bursts to discard to achieve zero slope in bprops
        """
        if not self.flags['calculated_slopes']:
            self.get_bprop_slopes()

        self.printv('Finding number of bursts to discard to ensure convergence')

        if self.flags['regress_too_few_bursts']:
            self.printv('Too few bursts to find self.discard, defaulting to min_discard')
            return self.parameters['min_discard']

        bursts = self.clean_bursts(exclude_min_regress=True)
        zero_slope = np.full(len(bursts), True)

        for bprop in self.regress_bprops:
            residuals = np.abs(bursts[f'slope_{bprop}'] / bursts[f'slope_{bprop}_err'])
            zero_slope = zero_slope & (residuals < 1)

        for burst_i, flat in zero_slope.iteritems():
            if flat:
                self.flags['converged'] = True
                return burst_i
        else:
            self.print_warn('Bursts not yet converged, using largest discard to satisfy min_regress')
            self.flags['converged'] = False
            return bursts.index[-1]

    def get_means(self):
        """Calculate mean burst properties
        """
        sec_day = 8.64e4

        if self.flags['too_few_bursts']:
            self.printv("Too few bursts to get average properties")
            self.summary['n_used'] = np.nan
            for bprop in (self.bprops + ['rate']):
                self.summary[bprop] = np.nan
                self.summary[f'u_{bprop}'] = np.nan
        else:
            bursts = self.clean_bursts(exclude_discard=True)
            self.summary['n_used'] = len(bursts)
            for bprop in self.bprops:
                values = bursts[bprop]
                self.summary[bprop] = np.mean(values)
                self.summary[f'u_{bprop}'] = np.std(values)

            self.summary['rate'] = sec_day / self.summary['dt']  # burst rate (per day)
            self.summary['u_rate'] = sec_day * self.summary['u_dt'] / self.summary['dt']**2

    def test_bimodal(self):
        """Determines if the burst sequence is bimodal
        """
        bursts = self.clean_bursts()
        n_bimodal = self.parameters['n_bimodal']
        if self.flags['too_few_bursts'] or len(bursts) < n_bimodal:
            self.printv('Too few bursts to check for bimodality')
            self.summary['bimodal'] = False
            return

        dt = np.sort(bursts.iloc[-n_bimodal:]['dt'])
        dt_lo, dt_hi = np.array_split(dt, 2)

        mean_lo = np.mean(dt_lo)
        mean_hi = np.mean(dt_hi)
        std_lo = np.std(dt_lo)
        std_hi = np.std(dt_hi)

        separation = (mean_hi - mean_lo) / np.sqrt(std_hi**2 + std_lo**2)
        self.summary['bimodal'] = separation > self.parameters['bimodal_sigma']

    def get_burst_dumps(self):
        """Identifies the first dumpfile (if any) immediately following each
            burst start time

        Note: if time difference greater than dump_time_min, that burst is skipped
        """
        self.bursts['dump_start'] = np.full(self.n_bursts, np.nan)
        try:
            self.check_dumpfiles()
        except NoDumps:
            return

        last_dump_index = self.dump_table.index[-1]
        t_offset = self.parameters['dump_time_offset']
        for burst in self.bursts.itertuples():
            idx = np.searchsorted(self.dump_table['time'], burst.t_start + t_offset)[0]
            if idx > last_dump_index:
                return
            cycle, time = self.dump_table.iloc[idx]
            if (time - burst.t_start) < self.parameters['dump_time_min']:
                self.bursts.loc[burst.Index, 'dump_start'] = cycle

    def check_stable_burning(self):
        """Attempts to identify if the model has become stable
        """
        self.printv('Checking for stable burning')

        if self.flags['too_few_bursts']:
            self.printv('Too few bursts to check for stable burning')
            self.summary['stable_burning'] = False
            return

        last_burst = self.bursts.t_peak.iloc[-1]
        last_timestep = self.lum[-1, 0]
        n_dt = (last_timestep - last_burst) / self.summary['dt']

        if n_dt > self.parameters['stable_dt_frac']:
            self.flags['stable_burning'] = True
            self.summary['stable_burning'] = True
            self.print_warn('Stable burning regime detected. Consider verifying')
        else:
            self.summary['stable_burning'] = False

    # ===========================================================
    # Plotting
    # ===========================================================
    def plot(self, peaks=True, display=True, save=False, log=True,
             burst_stages=False, candidates=False, legend=False, time_unit='h',
             short_wait=True, shocks=False, fontsize=14, title=True,
             outliers=True, show_all=False, dumps=False, dump_start=False):
        """Plots overall model lightcurve, with detected bursts
        """
        if not self.flags['lum_loaded']:
            self.load_lum_file()

        timescale = {'s': 1, 'm': 60, 'h': 3600, 'd': 8.64e4}.get(time_unit, 1)
        time_label = {'s': 's', 'm': 'min', 'h': 'hr', 'd': 'day'}.get(time_unit, 's')
        markersize = 10
        markeredgecolor = '0'
        dump_y = 1e37  # y-value to plot dump markers

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.set_xlabel(f'Time ({time_label})', fontsize=fontsize)

        if show_all:
            burst_stages = True
            candidates = True
            short_wait = True
            shocks = True
            outliers = True

        if title:
            ax.set_title(self.model_str)

        if log:
            yscale = 1
            ax.set_yscale('log')
            ax.set_ylim([1e34, 1e40])
            ax.set_ylabel('Luminosity (erg s$^{-1}$)', fontsize=fontsize)
        else:
            ax.set_ylabel('Luminosity ($10^{38}$ erg s$^{-1}$)', fontsize=fontsize)
            yscale = 1e38

        ax.plot(self.lum[:, 0]/timescale, self.lum[:, 1]/yscale, c='black')

        if not self.flags['analysed']:
            self.printv('Model not analysed. Only plotting raw lightcurve')
            self.show_save_fig(fig, display=display, save=save, plot_name='model')
            return

        if self.n_bursts == 0:
            self.printv('No bursts. Only plotting raw lightcurve')
            self.show_save_fig(fig, display=display, save=save, plot_name='model')
            return

        if candidates:  # NOTE: candidates may be modified if a shock was removed
            x = self.candidates[:, 0] / timescale
            y = self.candidates[:, 1] / yscale
            ax.plot(x, y, marker='o', c=self.colours['candidates'], ls='none',
                    markersize=markersize, markeredgecolor=markeredgecolor, label='Candidates')

        if peaks:
            ax.plot(self.bursts['t_peak']/timescale, self.bursts['peak']/yscale, marker='o', ls='none',
                    label='Bursts', markeredgecolor=markeredgecolor, markersize=markersize,
                    c=self.colours['bursts'])

        if outliers:
            bursts = self.outliers()
            x = bursts['t_peak'] / timescale
            y = bursts['peak'] / yscale
            ax.plot(x, y, marker='o', c=self.colours['outliers'], ls='none',
                    markeredgecolor=markeredgecolor, markersize=markersize, label='Outliers')

        if short_wait:
            if self.flags['short_waits']:
                bursts = self.short_waits()
                x = bursts['t_peak'] / timescale
                y = bursts['peak'] / yscale
                ax.plot(x, y, marker='o', c=self.colours['short_waits'], ls='none',
                        markersize=markersize, markeredgecolor=markeredgecolor, label='Short-wait')

        if burst_stages:
            for stage in ('pre', 'start', 'end'):
                x = self.bursts[f't_{stage}'] / timescale
                y = self.bursts[f'lum_{stage}'] / yscale
                label = {'pre': 'Burst stages'}.get(stage, None)
                ax.plot(x, y, marker='o', c=self.colours['burst_stages'], ls='none',
                        markersize=markersize, markeredgecolor=markeredgecolor, label=label)

        if shocks:  # plot shocks that were removed
            for i, shock in enumerate(self.shocks):
                idx = int(shock[0])
                shock_lum = shock[2]

                shock_slice = self.lum[idx-1:idx+2, :]
                shock_slice[1, 1] = shock_lum
                ax.plot(shock_slice[:, 0]/timescale, shock_slice[:, 1]/yscale,
                        c=self.colours['shocks'],
                        label='shocks' if (i == 0) else '_nolegend_')

        if dumps:
            if not self.flags['dumps_loaded']:
                self.load_dumpfiles()
            times = self.dump_table['time']
            ax.scatter(times/timescale, np.full_like(times, dump_y), marker='D',
                       color=self.colours['dumps'], label='dumps')

        if dump_start:
            burst_dumps = self.dumps_starts()
            times = burst_dumps['time']
            ax.scatter(times/timescale, np.full_like(times, dump_y), marker='D',
                       color='red', label='burst_dumps')

        if legend:
            ax.legend(loc=1, framealpha=1, edgecolor='0')
        self.show_save_fig(fig, display=display, save=save, plot_name='model')

    def plot_convergence(self, bprops=('rate', 'fluence', 'peak'), discard=None,
                         legend=False, display=True, save=False, fix_xticks=False,
                         short_waits=False, outliers=False, show_mean=False,
                         shaded=True, frac=True, line_style=''):
        """Plots individual and average burst properties along the burst sequence
        """
        self.ensure_analysed_is(True)
        markersize = 8
        markeredgecolor = '0'
        fontsize = 14

        if discard is None:
            discard = self.discard
        else:
            self.discard = discard

        if self.n_bursts < discard+2:
            print('Too few bursts to plot convergence')
            return

        y_units = {'tDel': 'hr', 'dt': 'hr', 'fluence': '10$^{39}$ erg',
                   'peak': '10$^{38}$ erg/s', 'rate': 'day$^{-1}$'}
        y_scales = {'tDel': 3600, 'dt': 3600,
                    'fluence': 1e39, 'peak': 1e38}

        fig, ax = plt.subplots(len(bprops), 1, figsize=(6, 8), sharex='all')
        bursts = self.clean_bursts()

        bursts_discard = self.clean_bursts(exclude_discard=True)
        bursts_short_waits = self.short_waits()
        bursts_outliers = self.outliers(unique=False)

        for i, bprop in enumerate(bprops):
            y_unit = y_units.get(bprop)
            y_scale = y_scales.get(bprop, 1.0)
            ax[i].set_ylabel(f'{bprop} ({y_unit})', fontsize=fontsize)

            if fix_xticks:
                ax[i].set_xticks(self.bursts['n'])
                if i != len(bprops)-1:
                    ax[i].set_xticklabels([])

            if show_mean:
                mean = None
                std = None
                for burst in bursts_discard.itertuples():
                    bslice = bursts_discard.loc[:burst.Index][bprop]
                    mean = np.mean(bslice) / y_scale
                    std = np.std(bslice) / y_scale
                    ax[i].errorbar(burst.n, mean, yerr=std,
                                   marker='o', c='C0', capsize=3, ls='none',
                                   markersize=markersize, markeredgecolor=markeredgecolor,
                                   label='cumulative mean' if burst.Index == bursts_discard.index[0] else '_nolegend_')
                self.printv(f'{bprop}: mean={mean:.3e}, std={std:.3e}, frac={std/mean:.3f}')

            if shaded:
                mean = np.mean(bursts_discard[bprop]) / y_scale
                std = np.std(bursts_discard[bprop]) / y_scale
                x = [discard+1, self.n_bursts]
                y = np.array([mean, mean])
                ax[i].plot(x, y, color='C0')
                ax[i].fill_between(x, y+std, y-std, color='0.8')

                if frac:
                    ax[i].text(x[1], 1.005*(y[1]+std), f'({100*std/mean:.1f}%)',
                               horizontalalignment='right')

            if outliers:
                ax[i].plot(bursts_outliers['n'], bursts_outliers[bprop] / y_scale,
                           marker='o', c=self.colours['outliers'], ls='none',
                           markersize=markersize, markeredgecolor=markeredgecolor,
                           label='Outliers')

            if short_waits:
                ax[i].plot(bursts_short_waits['n'], bursts_short_waits[bprop] / y_scale,
                           marker='o', c=self.colours['short_waits'], ls='none',
                           markersize=markersize, markeredgecolor=markeredgecolor,
                           label='Short waits')

            ax[i].plot(bursts['n'], bursts[bprop] / y_scale,
                       marker='o', c=self.colours['bursts'], ls=line_style,
                       markersize=markersize, markeredgecolor=markeredgecolor,
                       label='Bursts')
        if legend:
            ax[0].legend(loc=3)

        ax[0].set_title(self.model_str, fontsize=fontsize)
        ax[-1].set_xlabel('Burst num', fontsize=fontsize)
        plt.tight_layout()
        self.show_save_fig(fig, display=display, save=save, plot_name='convergence')

    def plot_linregress(self, display=True, save=False, short_waits=True,
                        outliers=True, legend=False, sigma=1):
        if self.flags['regress_too_few_bursts']:
            self.printv("Can't plot linregress: too few bursts to get slopes")
            return
        if not self.flags['calculated_slopes']:
            self.printv('Slopes not yet calculated')
            self.get_bprop_slopes()

        fig, ax = plt.subplots(3, 1, figsize=(6, 8), sharex='all')
        markersize = 8
        markeredgecolor = '0'
        fontsize = 14

        bursts_clean = self.clean_bursts(exclude_min_regress=True)
        bursts_outliers = self.outliers()
        bursts_short_waits = self.short_waits()
        x = bursts_clean['n']

        for i, bprop in enumerate(self.regress_bprops):
            ax[i].plot([0, self.n_bursts], [0, 0], ls='--', c='0', markersize=markersize)
            y = bursts_clean[f'slope_{bprop}']
            y_err = bursts_clean[f'slope_{bprop}_err'] * sigma
            ax[i].set_ylabel(bprop, fontsize=fontsize)

            if outliers:
                x_outliers = np.array(bursts_outliers['n'])
                ax[i].plot(x_outliers, np.zeros_like(x_outliers),
                           c=self.colours['outliers'], marker='o', ls='none',
                           markeredgecolor=markeredgecolor, markersize=markersize,
                           label='Outliers')

            if short_waits:
                x_short = np.array(bursts_short_waits['n'])
                ax[i].plot(x_short, np.zeros_like(x_short),
                           c=self.colours['short_waits'], marker='o', ls='none',
                           markeredgecolor=markeredgecolor, markersize=markersize,
                           label='Short waits')

            ax[i].errorbar(x, y, yerr=y_err,
                           c=self.colours['bursts'], ls='none', marker='o', capsize=3,
                           markersize=markersize, markeredgecolor=markeredgecolor,
                           label='Slopes')

        ax[-1].set_xlabel('Discarded bursts', fontsize=fontsize)
        ax[0].set_title(self.model_str)
        if legend:
            ax[0].legend()
        plt.tight_layout()
        self.show_save_fig(fig, display=display, save=save, plot_name='linregress')

    def save_burst_lightcurves(self, path=None):
        """Saves burst lightcurves to txt files. Excludes 'pre' bursts
        """
        self.ensure_analysed_is(True)
        if path is None:  # default to model directory
            path = self.paths['batch_models']

        for i in range(self.n_bursts):
            bnum = i + 1

            i_start = self.bursts['t_pre_i'][i]
            i_zero = self.bursts['t_start_i'][i]
            i_end = self.bursts['t_end_i'][i]

            t = self.lum[i_start:i_end, 0] - self.lum[i_zero, 0]
            lum = self.lum[i_start:i_end, 1]
            uncertainty = 0.02
            u_lum = lum * uncertainty

            lightcurve = np.array([t, lum, u_lum]).transpose()
            header = 'time luminosity u_luminosity'
            b_file = f'b{bnum}.txt'
            filepath = os.path.join(path, b_file)

            np.savetxt(filepath, lightcurve, header=header)

    def plot_lightcurves(self, bursts=None, save=False, display=True, log=False,
                         zero_time=True, fontsize=14, ylims=(-1, 8), **kwargs):
        """Plot individual burst lightcurve

        parameters
        ----------
        bursts : [int] (optional)
            list of burst indices to plot. Defaults to plotting all bursts
        save : bool (optional)
        display : bool (optional)
        log : bool (optional)
        zero_time : bool (optional)
        fontsize : int (optional)
        ylims : [int, int] (optional)
        """
        self.ensure_analysed_is(True)
        if not self.flags['lum_loaded']:
            self.load_lum_file()
        if bursts is None:
            bursts = np.arange(1, self.n_bursts)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.set_ylabel('Luminosity ($10^{38}$ erg s$^{-1}$)', fontsize=fontsize)
        ax.set_xlabel('Time (s)', fontsize=fontsize)
        ax.set_title(self.model_str)

        if log:
            ax.set_yscale('log')
            ax.set_ylim([1e34, 1e39])

        for burst in bursts:
            self.add_lightcurve(burst, ax, zero_time=zero_time, **kwargs)

        ax.set_xlim(left=-5, right=20)
        ax.set_ylim(ylims[0], ylims[1])
        plot_path = os.path.join(self.paths['plots'], 'lightcurves')

        self.show_save_fig(fig, display=display, save=save, plot_name='lightcurve',
                           path=plot_path, extra='')

    def add_lightcurve(self, burst, ax, zero_time=True, color='C0', alpha=1.0,
                       linewidth=1):
        """Add a lightcurve to the provided matplotlib axis

        parameters
        ----------
        burst : int
            index of burst to add (e.g. 0 for first burst)
        ax : matplotlib axis
            axis object to add lightcurves to
        zero_time : bool
        color : str
        alpha : flt
        linewidth : flt
        """
        yscale = 1e38
        if burst > self.n_bursts - 1\
                or burst < 0:
            raise ValueError(f'Burst index ({burst}) out of bounds '
                             f'(n_bursts={self.n_bursts})')

        i_start = self.bursts['t_pre_i'][burst]
        i_end = self.bursts['t_end_i'][burst]
        x = self.lum[i_start:i_end, 0]
        y = self.lum[i_start:i_end, 1]

        if zero_time:
            x = x - self.bursts['t_start'][burst]
        ax.plot(x, y / yscale, label=f'{burst}', color=color, alpha=alpha,
                linewidth=linewidth)

    def save_all_lightcurves(self, **kwargs):
        for burst in range(self.n_bursts):
            self.plot_lightcurves(burst, save=True, display=False, **kwargs)

    def plot_temp_profile(self, discard=5, legend=False, relative=False, plot_all=False,
                          **kwargs):
        """Plots temperature profile at each dump_start

        discard : int
            number of initial burst dumps to discard
        """
        if plot_all:
            cycles = self.dump_table.cycle
        else:
            cycles = np.array(self.dumps_starts().index)
        kepler_plot.plot_dump_profile(run=self.run, batch=self.batch, source=self.source,
                                      cycles=cycles[discard:], legend=legend,
                                      relative=relative, y_param='tn', **kwargs)

    def show_save_fig(self, fig, display, save, plot_name,
                      path=None, extra='', extension='png'):
        """Displays and/or Saves given figure

        parameters
        ----------
        fig : plt.Figure object
        display : bool
        save : bool
            save the figure to file (to fold in checking from other functions)
        plot_name : str
            type of plot being saved
        path : str (optional)
            path of diretcory to save to.
            If not provided, assumes there exists a folder [source]/plots/[plot_name]
        extra : str (optional)
            optional string to attach to filename
        extension : str (optional)
        """

        if save:
            filename = f'{plot_name}_{self.model_str}{extra}.{extension}'

            if path is None:
                path = os.path.join(self.paths['source'], 'plots', plot_name)
            filepath = os.path.join(path, filename)

            self.printv(f'Saving figure: {filepath}')
            if self.options['try_mkdir_plots']:
                grid_tools.try_mkdir(path, skip=True)
            fig.savefig(filepath)

        if display:
            plt.show(block=False)
        else:
            plt.close(fig)
