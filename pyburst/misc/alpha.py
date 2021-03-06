import numpy as np
from astropy import units

from pyburst.grids import grid_analyser
from pyburst.physics import gravity


def add_alpha(kgrid):
    """Adds alpha column to given Kgrid

    parameters
    ----------
    kgrid : grid_analyser.Kgrid
        grid object containing model data
    """
    add_redshift(kgrid)
    add_phi(kgrid)
    add_lum_acc(kgrid)
    add_acc_energy(kgrid)

    summ = kgrid.summ
    kgrid.summ['alpha'] = summ.acc_energy / summ.fluence
    kgrid.summ['u_alpha'] = summ.alpha * np.sqrt((summ.u_acc_energy / summ.acc_energy)**2
                                                 + (summ.u_fluence / summ.fluence)**2)


def add_lum_acc(kgrid):
    """Adds accretion luminosity column to given Kgrid

    parameters
    ----------
    kgrid : grid_analyser.Kgrid
        grid object containing model data
    """
    mdot_edd = 1.75e-8  # M_sun / yr
    msunyr_to_gramsec = (units.M_sun / units.year).to(units.g / units.s)
    check_column(kgrid.params, column='phi', label='params', remedy='add_phi()')

    mdot = kgrid.params.accrate * mdot_edd * msunyr_to_gramsec
    lum_acc = -mdot * kgrid.params.phi
    kgrid.params['lum_acc'] = lum_acc


def add_acc_energy(kgrid):
    """Adds accretion energy column to given Kgrid

    parameters
    ----------
    kgrid : grid_analyser.Kgrid
        grid object containing model data
    """
    check_column(kgrid.params, column='lum_acc', label='params', remedy='add_lum_acc()')
    kgrid.summ['acc_energy'] = kgrid.params.lum_acc * kgrid.summ.dt
    kgrid.summ['u_acc_energy'] = kgrid.params.lum_acc * kgrid.summ.u_dt


def add_redshift(kgrid, m_ratio=1.0):
    """Adds redshift (1+z) column to given Kgrid

    parameters
    ----------
    kgrid : grid_analyser.Kgrid
        grid object containing model data
    m_ratio : flt (optional)
        mass ratio, M_gr / M_newton
    """
    default_radius = 10

    if 'radius' not in kgrid.params.columns:
        print('Using default radius=10km')
        kgrid.params['radius'] = default_radius

    radii = np.array(kgrid.params.radius)
    masses = np.array(kgrid.params.mass)

    r_ratios, redshifts = gravity.gr_corrections(r=radii, m=masses, phi=m_ratio)
    kgrid.params['radius_gr'] = radii * r_ratios
    kgrid.params['mass_gr'] = masses * m_ratio
    kgrid.params['redshift'] = redshifts


def add_phi(kgrid):
    """Adds phi (gravitational potential) column to given Kgrid

    parameters
    ----------
    kgrid : grid_analyser.Kgrid
        grid object containing model data
    """
    check_column(kgrid.params, column='redshift', label='params', remedy='add_redshift()')

    phi = gravity.get_potential_gr(redshift=kgrid.params.redshift)
    kgrid.params['phi'] = phi


def check_column(table, column, label, remedy):
    """Checks if column exists in table

    parameters
    ----------
    table : pd.DataFrame
        table to check for columns
    column : str
        name of column to check for
    label : str
        name of table
    remedy : str
        suggested function to use
    """
    if column not in table.columns:
        raise ValueError(f'No {column} column in kgrid.{label}, try using {remedy}')
