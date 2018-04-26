#
#
# Copyright (C) 2013 Patricio Rojo
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 2 of the GNU General 
# Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, 
# Boston, MA  02110-1301, USA.
#
#
from __future__ import print_function, division

import dataproc as dp
import scipy as sp
import warnings
import copy
import sys
import pdb
from astropy.utils.exceptions import AstropyUserWarning

import logging
io_logger = logging.getLogger('dataproc.io')


class AstroDir(object):
    """Collection of AstroFile.

    Several recursive methods that are applied to each AstroFile are available

    Parameters
    ----------
    path : str or list or AstroFile
        Contains information from the file list. If str, a directory+wildcard it is assumed,
        and parsed by `glob.glob`
    mbias, mflat : see `.add_mbias()` or `.add_mflat()`
        Master bias and flat to associate to each AstroFile (in one shared AstroCalib object)
    calib_force : bool
        If True, then force specified `mbias` and `mflat` to all files, otherwise
        assign it only if it doesn't have one already.
    read_keywords : list
        read all specified keywords at creation time and store it in cache
    hdu : int
        default HDU
    hdud : int
        default HDU for data
    hduh : int
        default HDU for the header

    Attributes
    ----------
    files : list
        Contains the list of all AstroFile that belong to this AstroDir.

    See Also
    --------
    AstroCalib : Object that holds calibration information. One of them can be shared
        by many AstroFile
    """

    def __init__(self, path, mflat=None, mbias=None,
                 mbias_header=None, mflat_header=None,
                 calib_force=False, read_keywords=None,
                 hdu=0, hdud=None, hduh=None, auto_trim=None,
                 jd_from_ut=None):
        import os
        import glob
        import os.path as pth
        files = [ ]

        if hduh is None:
            hduh = hdu
        if hdud is None:
            hdud = hdu

        if isinstance(path, str):
            file_n_dir = glob.glob(path)
        elif isinstance(path, dp.AstroFile):
            file_n_dir = [path]
        else:
            file_n_dir = path
        for f in file_n_dir:
            if isinstance(f, dp.AstroFile):
                nf = copy.deepcopy(f)
            elif pth.isdir(f):
                for sf in os.listdir(f):
                    nf = dp.AstroFile(f + '/' + sf, hduh=hduh, hdud=hdud, read_keywords=read_keywords, auto_trim=auto_trim)
                    if nf:
                        files.append(nf)
                nf = False
            else:
                nf = dp.AstroFile(f, hduh=hduh, hdud=hdud, read_keywords=read_keywords, auto_trim=auto_trim)
            #pdb.set_trace()
            if nf:
                files.append(nf)
            #pdb.set_trace()

        self.files = files
        self.props = {}
        calib = dp.AstroCalib(mbias, mflat, auto_trim=auto_trim,
                              mbias_header=mbias_header, mflat_header=mflat_header)
        
        for f in files:
            if calib_force or not f.has_calib():  # allows some of the files to keep their calibration
                # AstroFile are created with an empty calib by default, which is overwritten here.
                #  Hoping that garbage collection works:D
                f.calib = calib

        self.path = path

        if jd_from_ut is not None:
            if len(jd_from_ut) != 2:
                raise TypeError("jd_from_ut parameter need to be a 2-element tuple: source, target. See help on method .jd_from_ut()")
            self.jd_from_ut(*jd_from_ut)

    def add_bias(self, mbias):
        """Update master bias in all the calibration objects in this AstroDir.

        Parameters
        ----------
        mbias : dict or array_like
            Master Bias to use for all frames.

        See Also
        --------
        dataproc.AstroCalib.add_bias : this function is called for
            each unique AstroCalib object in AstroDir
        """
        unique_calibs = set([f.calib for f in self])
        for c in unique_calibs:
            c.add_bias(mbias)

    def add_flat(self, mflat):
        """Update Master Flats in all the calibration objects in this AstroDir.

        Parameters
        ----------
        mflat : dict or array_like
            Master Flat to use for all frames.

        See Also
        --------
        dataproc.AstroCalib.add_flat : this function is called for
            each unique AstroCalib object in AstroDir
        """
        unique_calibs = set([f.calib for f in self])
        for c in unique_calibs:
            c.add_flat(mflat)

    def sort(self, *args, **kwargs):
        """ Return sorted list of files according to specified header field, use first match.
            It uses in situ sorting, but returns itself"""
        if len(args) == 0:
            raise ValueError("At least one valid header field must be specified to sort")
        hdrfld = False

        for a in args:
            if self.getheaderval(a):
                hdrfld = a
                break
        if not hdrfld:
            raise ValueError(
                "A valid header field must be specified to use as a sort key."
                " None of the currently requested were found: %s" % (', '.join(args),))

        # Sorting is done using python operators __lt__, __gt__, ... who are inquired by .sort() directly.
        for f in self:
            f.add_sortkey(hdrfld)
        self.files.sort()
        return self

    def __repr__(self):
        return "<AstroFile container: %s>" % (self.files.__repr__(),)

    def __add__(self, other):
        if isinstance(other, AstroDir):
            other_af = other.files
        elif isinstance(other, (list, tuple)) and isinstance(other[0], str):
            io_logger.warning("Adding list of files to Astrodir, calib and hdu defaults"
                             " will be shared from first AstroFile in AstroDir")
            other_af = [dp.AstroFile(filename,
                                     hdud=self[0]._hdud,
                                     hduh=self[0]._hduh,
                                     mflat=self[0].calib.mflat,
                                     mbias=self[0].calib.mbias)
                        for filename in other]
        else:
            raise TypeError("Cannot add {} + {}", self.__class__, other.__class__)

        return dp.AstroDir(self.files+other_af)

    def __getitem__(self, item):
        # imitate indexing on boolean array as in scipy.
        if isinstance(item, sp.ndarray):
            if item.dtype == 'bool':
                if len(item) != len(self):
                    raise ValueError("Attempted to index AstroDir with a boolean array "
                                     "of different size (it must include all bads)")

                fdir = [f for b, f in zip(item, self) if b]
                return AstroDir(fdir)

        elif isinstance(item, slice):
            return AstroDir(self.files.__getitem__(item))

        return self.files[item]  # .__getitem__(item)

    def __len__(self):
        return len(self.files)

    def stats(self, *args, **kwargs):
        """
Return stats
        :param args: Specify the stats that want to be returned
        :param kwargs: verbose_headings is the only keyword accepted to print a heading
        :return: the stat as returned by each of the AstroFiles
        """
        verbose_heading = kwargs.pop('verbose_heading', True)
        extra_headers = kwargs.pop('extra_headers', True)
        if kwargs:
            raise SyntaxError("only the following keyword arguments for stats are accepted 'verbose_heading', 'extra_headers'")
        ret = []
        for af in self:
            ret.append(af.stats(*args, verbose_heading=verbose_heading, extra_headers=extra_headers))
            verbose_heading = False
        return ret

    def filter(self, *args, **kwargs):
        """ Filter files according to those whose filter return True to the given arguments.
            What the filter does is type-dependent in each file. Check docstring of a single element."""
        from copy import copy
        new = copy(self)
        new.files = [f for f in self if f.filter(*args, **kwargs)]
        return new

    def basename(self, joinchr=', '):
        """Returns the basename of the files in object"""
        return joinchr.join([b.basename() for b in self])

    def getheaderval(self, *args, **kwargs):
        """ Gets the header values specified in 'args' from each of the files.
            Returns a simple list if only one value is specified, or a list of tuples otherwise
            :param cast: output function
            :param single_in_list: default False
            """
        if 'single_in_list' in kwargs:
            single_in_list = kwargs['single_in_list']
        else:
            single_in_list = False

        if 'cast' in kwargs:
            cast = kwargs['cast']
        else:
            if len(args) == 1 and not single_in_list:
                cast = lambda x: x[0]
            else:
                cast = lambda x: x

        warnings.filterwarnings("once", "non-standard convention", AstropyUserWarning)
        ret = [f.getheaderval(*args, cast=cast, **kwargs) for f in self]
        try:
            while True:
                idx = ret.index(None)
                logging.warning("Removing file with defective header from AstroDir")
                self.files.pop(idx)
                ret.pop(idx)
        except ValueError:
            pass

        warnings.resetwarnings()
        return ret

    def setheader(self, **kwargs):
        """ Sets the header values specified in 'args' from each of the files.
            Returns a simple list if only one value is specified, or a list of tuples otherwise
"""
        if False in [f.setheader(**kwargs) for f in self]:
            raise ValueError("Setting the header of a file returned error... panicking!")

        return self

    def get_datacube(self, normalize_region=None, normalize=False, verbose=False,
                     check_unique=None, group_by=None):
        """
Returns all data from the AstroFiles in a datacube
        :param group_by:
        :param normalize_region:
        :param normalize:
        :param verbose:
        :param check_unique: receives a list of headers that need to be checked for uniqueness.
        :return:
        """
        #pdb.set_trace()
        if verbose:
            print("Reading {} good frames{}: ".format(len(self),
                                                      normalize and " and normalizing" or ""),
                  end='')
        if check_unique is None:
            check_unique = []
        if normalize_region is None:
            if 'normalize_region' in self.props:
                normalize_region = self.props['normalize_region']
            else:
                normalize_region = slice(None)

        grouped_data = {}

        # check uniqueness... first get the number of unique header values for each requested keyword
        # and then complain if any greater than 1
        if len(check_unique) > 1:
            lens = sp.array([len(set(rets)) for rets in zip(*self.getheaderval(*check_unique))])
        elif len(check_unique) == 1:
            lens = sp.array([len(set(self.getheaderval(*check_unique)))])
        else:
            lens = sp.array([])
        if True in (lens > 1):
            raise ValueError("Header(s) {} are not unique in the input dataset".
                             format(", ".join(sp.array(check_unique)[lens > 1])))

        for af in self:
            data = af.reader()
            if normalize:
                data /= data[normalize_region].mean()
            group_key = af[group_by]
            if group_key not in grouped_data.keys():
                grouped_data[group_key] = []
            grouped_data[group_key].append(data)

            if verbose:
                print(".", end='')
                sys.stdout.flush()

        if None in grouped_data and len(grouped_data) > 1:
            #todo check error message
            raise ValueError("Panic. None should have been key of grouped_data only if group_by was None. "
                            "In such case, it should have been alone.")

        for g in grouped_data:
            grouped_data[g] = sp.array(grouped_data[g])

        if verbose:
            print("")

        return grouped_data


    def pixel_xy(self, xx, yy, normalize_region=None, normalize=False,
             check_unique=None, group_by=None):
        """
Returns pixel at (xx,yy) position for all frames

        :param group_by: If set, then group by the specified header returning an [n_unique, n_y, n_x] array
        :param normalize_region: Subregion to use for normalization
        :param normalize:  Whether to Normalize
        :param check_unique: Check uniqueness in header
        :return:  mean of frames. If group_by is set, it returns a dictionary keyed by this group
        """
        if check_unique is None:
            check_unique = []
        if group_by in check_unique:
            check_unique.pop(check_unique.index(group_by))

        data_dict = self.get_datacube(normalize_region=normalize_region,
                                      normalize=normalize,
                                      check_unique=check_unique,
                                      group_by=group_by)

        groupers = sorted(data_dict.keys())
        ret = [data_dict[g][:, yy, xx] for g in groupers]


        if len(groupers) > 1:
            return {g: r for r,g in zip(ret, groupers)}
        else:
            return ret[0]


        # todo: return AstroFile


    def median(self, normalize_region=None, normalize=False, verbose=True,
               check_unique=None, group_by=None):
        """

        :param group_by: If set, then group by the specified header returning an [n_unique, n_y, n_x] array
        :param normalize_region: Subregion to use for normalization
        :param normalize:  Whether to Normalize
        :param verbose:   Output progress indicator
        :param check_unique: Check uniquenes in heaeder
        :return:  median of frames. If group_by is set, it returns a dictionary keyed by this group
        """
        if check_unique is None:
            if normalize:
                check_unique = []
            else:
                check_unique = ['exptime']
        if group_by in check_unique:
            check_unique.pop(check_unique.index(group_by))

        data_dict = self.get_datacube(normalize_region=normalize_region,
                                      normalize=normalize,
                                      verbose=verbose,
                                      check_unique=check_unique,
                                      group_by=group_by)

        if verbose:
            print("Median combining{}".format(group_by is not None and ' grouped by "{}":'.format(group_by) or ""),
                  end='')
            sys.stdout.flush()
        groupers = sorted(data_dict.keys())
        ret = sp.zeros([len(groupers)] + list(data_dict[groupers[0]][0].shape))
        for k in range(len(groupers)):
            if verbose and group_by is not None:
                print("{} {}".format(k and "," or "", groupers[k]), end='')
                sys.stdout.flush()
            ret[k, :, :] = sp.median(data_dict[groupers[k]], axis=0)
        if verbose:
            print(". done.")
            sys.stdout.flush()

        if len(groupers) > 1:
            return {g: r for r,g in zip(ret, groupers)}
        else:
            return ret[0]
        # todo: return AstroFile

    def mean(self, normalize_region=None, normalize=False, verbose=True,
             check_unique=None, group_by=None):
        """

        :param group_by: If set, then group by the specified header returning an [n_unique, n_y, n_x] array
        :param normalize_region: Subregion to use for normalization
        :param normalize:  Whether to Normalize
        :param verbose: Output progress indicator
        :param check_unique: Check uniqueness in header
        :return:  mean of frames. If group_by is set, it returns a dictionary keyed by this group
        """
        if check_unique is None:
            if normalize:
                check_unique = []
            else:
                check_unique = ['exptime']
        if group_by in check_unique:
            check_unique.pop(check_unique.index(group_by))

        data_dict = self.get_datacube(normalize_region=normalize_region,
                                      normalize=normalize,
                                      verbose=verbose,
                                      check_unique=check_unique,
                                      group_by=group_by)

        if verbose:
            print("Mean combining{}".format(group_by is not None and ' grouped by "{}":'.format(group_by) or ""),
                  end='')
            sys.stdout.flush()
        groupers = sorted(data_dict.keys())
        ret = sp.zeros([len(groupers)] + list(data_dict[groupers[0]][0].shape))
        for k in range(len(groupers)):
            if verbose and group_by is not None:
                print("{} {}".format(k and "," or "", groupers[k]), end='')
                sys.stdout.flush()
            ret[k, :, :] = sp.mean(data_dict[groupers[k]], axis=0)
        if verbose:
            print(": done.")
            sys.stdout.flush()

        if len(groupers) > 1:
            return {g: r for r,g in zip(ret, groupers)}
        else:
            return ret[0]
        # todo: return AstroFile

    # todo: add support for giving variance
    def lin_interp(self, target=0,
                   verbose=True, field='EXPTIME',
                   check_unique=None, group_by=None):
        """Linear interpolate to given target value of the field 'field'.

        :param group_by: If set, then group by the specified header returning an [n_unique, n_y, n_x] array
        :param verbose: Output progress indicator
        :param check_unique: Check uniqueness in header
        :param target: Target value for the interpolation
        :return:  mean of frames. If group_by is set, it returns a dictionary keyed by this group
"""
        if check_unique is None:
            check_unique = []
        if group_by in check_unique:
            check_unique.pop(check_unique.index(group_by))

        data_dict = self.get_datacube(verbose=verbose,
                                      check_unique=check_unique,
                                      group_by=group_by)

        if verbose:
            print("Linear interpolating{}".format(group_by is not None and ' grouped by "{}":'.format(group_by) or ""),
                  end='')
            sys.stdout.flush()
        groupers = sorted(data_dict.keys())
        ret = sp.zeros([len(groupers)] + list(data_dict[groupers[0]][0].shape))
        for k in range(len(groupers)):
            if verbose and group_by is not None:
                print("{} {}".format(k and "," or "", groupers[k]), end='')
                sys.stdout.flush()

            data_cube = data_dict[groupers[k]]
            values = self.getheaderval(field)
            values, data_cube = dp.sortmanynsp(values, data_cube)

            if not (values[0] <= target <= values[-1]):
                io_logger.warning("Target value for interpolation ({})\n outside "
                                  "the range of chosen keyword {}: [{}, {}]."
                                  "\nCannot interpolate".format(target, field,
                                                                values[0], values[-1]))
                return None

            for j in range(data_cube[0].shape[1]):
                for i in range(data_cube[0].shape[0]):
                    ret[k,j,i] = sp.interp(target, values, data_cube[:,j,i])
        if verbose:
            print(". done.")
            sys.stdout.flush()

        if len(groupers) > 1:
            return {g: r for r,g in zip(ret, groupers)}
        else:
            return ret[0]



        #
        # import scipy as sp
        # def pvns(pfret,target):
        #     """Reconstructs polyfit to target value and sigma"""
        #     p,cov=pfret
        #     val = p[0]*target + p[1]
        #     var = cov[0,0]*target**2 + cov[1,1] + 2*target*cov[1,0]
        #     return val,var
        #
        #
        # def getlinterp(params, pool=None):
        #     """Evaluate line interpolation """
        #     ##TD: being called for wgt and nwgt
        #     dowgt = lambda fv,target,dat,wgt: sp.array([pvns(sp.polyfit(fv, dt, 1,
        #                                                                 w=w, cov=True),
        #                                                      target)
        #                                                 for dt,w in zip(dat,wgt)]
        #                  )
        #     donwgt = lambda fv,target,dat: sp.array([pvns(sp.polyfit(fv, dt, 1), target)
        #                   for dt in dat])
        #     dofcn = (len(params)==4) and dowgt or donwgt
        #     if pool is None:  #Can't use ...and...or... or it will execute twice!
        #         return dofcn(*params)
        #     else:
        #         return pool.apply_async(dofcn,params)
        #
        # if not target:
        #     raise ValueError("keyword target=value must be specified for lineinterp(), where value cannot be zero.")
        #
        # arr=self.arrays[self.okframes]
        # if var is None:
        #     var=self.sigmas[self.okframes]**2
        # hd = [h for h,o in zip(self.headers,self.okframes) if o]
        # fv = sp.array([h[field] for h in hd])
        #
        # import warnings
        # from numpy import __version__ as vrs
        # if float(vrs[0:3])<1.7:
        #     raise ValueError("numpy version must be at least 1.7.  Otherwise polyfit() cannot handle weights")
        # if (fv==fv[0]).all():
        #     raise ValueError("Cannot linear-interpolate since all values of field '%s' are identical in the data" % field)
        # if len([h for h in hd if (self.flagfield in h)]):
        #     warnings.warn("Interpolating in a list of frames who did not all had header with the target field")
        # if target<min(fv) or target>max(fv):
        #     warnings.warn("Requested interpolation target (%f) is beyond the range of the '%s' field in the frames (%f - %f)" %(target,field,min(fv),max(fv)))
        #
        # print ("  sorting data%s"
        #        % (doerr and  " and weights" or "",))
        # sh = arr.shape
        # fldata = arr.reshape(sh[0],sp.array(sh[1:]).prod())
        # flwgt = 1.0/var.reshape(sh[0],sp.array(sh[1:]).prod())
        # fv,fldata,flwgt = sortmanynsp(fv,fldata,flwgt)
        #
        #
        # from multiprocessing.pool import ThreadPool
        # print("  evaluating linear fit to %i pixels"
        #       % (fldata.shape[1],))
        # if doerr:
        #     pool=multi>1 and ThreadPool(processes=multi) or None
        #     print ("   using %i processors" % (multi,) )
        #     delta = int(fldata.shape[1]/multi+0.999)
        #     multistart = [[delta*i,delta*(i+1)] for i in range(multi)]
        #     multistart[-1][1] = fldata.shape[1]
        #
        #     mpool = [getlinterp((fv, target,
        #                          fldata.T[i0:i1,:],
        #                          flwgt.T[i0:i1,:]),
        #                         pool=pool)
        #              for i0,i1 in multistart]
        #     if(len(mpool)>1):
        #         tmp=[]
        #         for mp in mpool:
        #             tmp.extend(mp.get())
        #         tmp=sp.array(tmp)
        #     else:
        #         tmp=mpool[0]
        #
        #     # else:
        #     #     tmp = getlinterp((fv,target,fldata.T,flwgt.T))
        # else:
        #     print(" - Requested to avoid error estimation")
        #     tmp = sp.array([sp.polyval(sp.polyfit(fv, dt, 1), target)
        #                     for dt in zip(fldata.T)])
        # comb = tmp[:,0].reshape(sh[1:])
        # sig = tmp[:,1].reshape(sh[1:])
        # self.data=comb
        # self.sigma=sig
        # self.lastmet=('lininterp',target,field,sigma, doerr)
        # self.ncombine = len(arr)
        # self._updatehdr(exptime=target)
        # return self

        
    def std(self, normalize_region=None, normalize=False, verbose=True,
             check_unique=None, group_by=None):
        """
        Get pixel by pixel standard deviation within files.

        :param group_by: If set, then group by the specified header returning an [n_unique, n_y, n_x] array
        :param normalize_region: Subregion to use for normalization
        :param normalize:  Whether to Normalize
        :param verbose: Output progress indicator
        :param check_unique: Check uniqueness in header
        :return:  standard deviation of frames. If group_by is set, it returns a dictionary keyed by this group
        """
        if check_unique is None:
            if normalize:
                check_unique = []
            else:
                check_unique = ['exptime']
        if group_by in check_unique:
            check_unique.pop(check_unique.index(group_by))

        data_dict = self.get_datacube(normalize_region=normalize_region,
                                      normalize=normalize,
                                      verbose=verbose,
                                      check_unique=check_unique,
                                      group_by=group_by)

        if verbose:
            print("Obtaining Standard Deviation{}".format(group_by is not None
                                                          and ' grouped by "{}":'.format(group_by) or ""),
                  end='')
            sys.stdout.flush()
        groupers = sorted(data_dict.keys())
        ret = sp.zeros([len(groupers)] + list(data_dict[groupers[0]][0].shape))
        for k in range(len(groupers)):
            if verbose and group_by is not None:
                print("{} {}".format(k and "," or "", groupers[k]), end='')
                sys.stdout.flush()
            ret[k, :, :] = sp.std(data_dict[groupers[k]], axis=0)
        if verbose:
            print(". done.")
            sys.stdout.flush()

        if len(groupers) > 1:
            return {g: r for r,g in zip(ret, groupers)}
        else:
            return ret[0]
        # todo: return AstroFile



    def jd_from_ut(self, target='jd', source='date-obs'):
        """
Add jd in header's cache to keyword 'target' using ut on keyword 'source'
        :param target: target keyword for JD storage
        :param source: input value in UT format
        """
        for af in self:
            af.jd_from_ut(target, source)

        return self

