
import time
import numpy as np

from mdreg import elastix, skimage, utils, plot, models


def fit(moving,
        fit_pixel = None,
        fit_image = None,
        fit_coreg = None,
        precision = 1.0,
        maxit = 3,
        verbose = 0,
        plot_params = None,
    ):

    """
    Fit a signal model to a series of images and perform coregistration to 
    correct for motion artefacts.

    Parameters
    ----------
    moving : numpy.array
        The series of images to be corrected. For more detail see table 
        :ref:`variable-types-table`.
    fit_pixel : dict, optional
        The parameters for fitting the signal model to each pixel, consisiting
        of, if required, of arguements for inbuilt function :func:`fit_pixels`. 
        The default 
        is None.
    fit_image : dict, optional
        The parameters for fitting the signal model to the whole image. The 
        default is None, which will apply the inbuilt :func:`constant` model fit. 
        For more detail see table :ref:`fit-image-table`.
    fit_coreg : dict, optional
        The parameters for coregistering the images. The default is None, which 
        uses the default elastix package setting. For more detail see table 
        :ref:`fit-coreg-table`.
    precision : float, optional
        The precision of the coregistration. The default is 1.0.
    maxit : int, optional
        The maximum number of iterations. The default is 3.
    verbose : int, optional
        The level of feedback to provide to the user. 0: no feedback; 1: text 
        output only; 2: text output and progress bars; 3: text output, progress 
        bars and image exports. The default is 0.
    plot_params : dict, optional
        The parameters for plotting the images. The default is None, which 
        creates an empty dictionary. For more detail see table 
        :ref:`plot-param-table`.
    
    Returns
    -------
    coreg : numpy.array
        The coregistered images.
    defo : numpy.array
        The deformation field.
    fit : numpy.array
        The fitted signal model.
    pars : dict
        The parameters of the fitted signal model.

    
    Please see :ref:`variable-types-table` for more detail on the returned 
    variables.
        
    """
    if fit_image is None:
        fit_image = {'func': models.constant,}
    
    if fit_coreg is None:
        fit_coreg = {'package': 'elastix',}
    
    if 'package' not in fit_coreg:
            fit_coreg['package'] = 'elastix'

    if plot_params is None:
        plot_params = {}

    coreg, defo = utils._init_output(moving)
    converged = False
    it = 1
    start = time.time()

    while not converged: 

        startit = time.time()

        # Fit signal model
        if verbose > 0:
            print('Fitting signal model (iteration ' + str(it) + ')')
        if fit_pixel is not None:
            fit_pixel['progress_bar'] = verbose>1
            fit, pars = utils.fit_pixels(coreg, **fit_pixel)
        else:
            fit_func = fit_image['func']
            kwargs = {i:fit_image[i] for i in fit_image if i!='func'}
            kwargs['progress_bar'] = verbose>1
            fit, pars = fit_func(coreg, **kwargs)

        # Fit deformation
        if verbose > 0:
            print('Fitting deformation field (iteration ' + str(it) + ')')
        
        fit_coreg['progress_bar'] = verbose>1
        coreg, defo_new = _coreg_series(moving, fit, **fit_coreg)

        # Check convergence
        corr = np.amax(np.linalg.norm(defo-defo_new, axis=-2))
        converged = corr <= precision 
        defo = defo_new
        
        if verbose > 0:
            print('Deformation correction after iteration ' + str(it) + ': ' + str(corr) + ' pixels')
            print('Calculation time for iteration ' + str(it) + ': ' + str((time.time()-startit)/60) + ' min')  
        if verbose==3:
            anim = plot.plot_series(moving, fit, coreg, filename='mdreg['+str(it)+']', **plot_params)

        if it == maxit: 
            break

        it += 1 

    if verbose > 0:
        print('Total calculation time: ' + str((time.time()-start)/60) + ' min')

    return coreg, defo, fit, pars



def _coreg_series(moving, fit, package='elastix', **coreg_params):

    if package == 'elastix':
        return elastix.coreg_series(moving, fit, **coreg_params)
    elif package == 'skimage':
        return skimage.coreg_series(moving, fit, **coreg_params)
    else:
        raise NotImplementedError('This coregistration package is not implemented')
