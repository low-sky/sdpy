import numpy as np
from image_registration.tests.registration_testing import make_extended



def determine_angle(image):
    """
    DEPRECATED
    """
    psd = AG_fft_tools.PSD2(image)
    # More difficult than I had guessed...
    # need to determine a 'weighting region' (say, where the power
    # is within 10^-4 of the peak?) and fft-zoom on that, then do an
    # azavg
    # Ignore central pixel - it confuses the radial average
    psd[psd.shape[0]/2, psd.shape[1]/2] = 0
    azprof = AG_image_tools.radialAverage(psd, symmetric=1)
    peak = azprof.max()
    theta = azprof.argmax()

    # Check for high secondary peaks
    roll = 20-theta
    nextpk = np.roll(azprof,roll)[40:].max()
    if nextpk/peak > 0.5:
        raise ValueError("There is a secondary peak >1/2 the primary peak and"
                         " offset by >20 degrees.  'plait' will not do much.")

    return theta

def plait_cube(cubes, angles, scale):

    if len(cubes) != len(angles):
        raise ValueError("Must provide the same number of images and angles.")

    if any(cubes.shape != cubes[0].shape for im in images):
        raise ValueError("Images must have the same shape")

    outcube = np.zeros_like(cubes[0])

    for ind in xrange(cubes[0].shape[0]):
        outcube[ind, :, :] = plait_plane([c[ind,:,:]
                                          for c in cubes],
                                         angles,
                                         scale)

    return outcube

def plait_plane(images, angles, scales):
    """
    Combine N images taken at N scan angles by suppressing large angular scales
    along the scan direction in all of them.

    Parameters
    ----------
    images : list of np.ndarray
    angles : list of float
        Angles in degrees (reference is the vector [1,0] in Cartesian
        coordinates)
    scale : float
        The width of the gaussian by which each image will be downweighted in
        the scan direction
    """

    if len(images) != len(angles):
        raise ValueError("Must provide the same number of images and angles.")

    if any(im.shape != images[0].shape for im in images):
        raise ValueError("Images must have the same shape")

    accum_wt = np.zeros_like(images[0])
    accum_ft = np.zeros_like(images[0], dtype=np.complex)
    accum_whnan = np.zeros_like(images[0], dtype='bool')
    for angle, image in zip(angles, images):
        wt = weighting(image, angle, scale)

        # Suppress NaNs: they become zero
        whnan = ~np.isfinite(image)
        accum_whnan |= whnan

        if np.count_nonzero(whnan) > 0:
            image[whnan] = 0

        ft = np.fft.fftshift(np.fft.fft2(image)) * wt
        accum_wt += wt
        accum_ft += ft

    final_ft = accum_ft / accum_wt
    final_image = np.fft.ifft2(np.fft.fftshift(final_ft))
    final_image[accum_whnan] = np.nan
    return final_image.real

def weighting(image, theta, sigma, min_wt=0.1):
    """
    Determine the weighting for fourier combination.
    The weight function is a Gaussian with rotation specified
    by theta in degrees from horizontal
    """
    y,x = np.indices(image.shape)
    y = y-image.shape[0]/2.
    x = x-image.shape[1]/2.
    #xrot = x * -np.cos(theta/180.*np.pi) + y * np.sin(theta/180.*np.pi)
    yrot = x * np.sin(theta/180.*np.pi) + y * np.cos(theta/180.*np.pi)

    weight = 1.0 - (1-min_wt)*np.exp(-yrot**2/(2.*sigma**2))
    return weight


def test(scale=3, size=256, amplitude=1, seed=0):
    np.random.seed(0)
    real_im = make_extended(size)
    m0 = add_stripe_noise(real_im, amplitude, axis=0)
    m1 = add_stripe_noise(real_im, amplitude, axis=1)
    rebuilt_im = plait([m0,m1], [0,90], scale)
    bad = m0+m1
    return real_im, rebuilt_im, bad, [m0,m1]

def add_stripe_noise(image, amplitude, axis=0, powerlaw=1.0):
    xx = np.indices(image.shape)[axis]
    imsize = image.shape[axis]
    xcen = imsize/2-(1-imsize%2) 
    xx -= xcen
    
    powermap = (np.random.randn(*image.shape) * xx**(-powerlaw)+
                np.random.randn(*image.shape) * xx**(-powerlaw) * 1j)
    powermap[powermap!=powermap] = 0

    stripe_map = np.abs(np.fft.fftshift(np.fft.fft(powermap,
                                                   axis=axis)))

    return image + amplitude*stripe_map
