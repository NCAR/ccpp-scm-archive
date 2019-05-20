#!/usr/bin/env python

from configobj import ConfigObj, flatten_errors
from validate import Validator
import argparse
import glob
import os
from netCDF4 import Dataset
import datetime
import numpy as np
import f90nml
import gmtb_scm_plotting_routines as gspr
import pandas as pd
import bisect
import gmtb_scm_read_obs as gsro

Rd = 287.0
Rv = 461.0

reload(gspr)
reload(gsro)

#subroutine for printing progress to the command line
def print_progress(n_complete, n_total):
    print str(n_complete) + ' of ' + str(n_total) + ' complete: (' + str(100.0*n_complete/float(n_total)) + '%)'

#set up command line argument parser to read in name of config file to use
parser = argparse.ArgumentParser()
parser.add_argument('config', help='configuration file for GMTB SCM analysis', nargs=1)

args = parser.parse_args()

#read in the configuration file specified on the command line (check against the configspec.ini file for validation)
config = ConfigObj(args.config[0],configspec="configspec_ens.ini")
validator = Validator()
results = config.validate(validator)

#standardized output for config file validation errors (quit if error)
if results != True:
    for (section_list, key, _) in flatten_errors(config, results):
        if key is not None:
            print 'The "%s" key in the section "%s" failed validation' % (key, ', '.join(section_list))
        else:
            print 'The following section was missing:%s ' % ', '.join(section_list)
    print 'Since GMTB SCM analysis configuration file did not pass validation, the program will quit.'
    quit()

#get the config file variables
gmtb_scm_datasets = config['gmtb_scm_datasets']
gmtb_scm_datasets_labels = config['gmtb_scm_datasets_labels']
obs_file = config['obs_file']
obs_compare = config['obs_compare']
plot_dir = config['plot_dir']
time_slices = config['time_slices']
plot_ind_datasets = config['plot_ind_datasets']
time_series_resample = config['time_series_resample']
skill_scores_val = True

plots = config['plots']
profiles_mean = plots['profiles_mean']
time_series = plots['time_series']
#contours = plots['contours']
profiles_mean_multi = plots['profiles_mean_multi']
time_series_multi = plots['time_series_multi']
scatters_mean = plots['scatters_mean']

#keep track of progress
#num_base_plots = len(time_slices)*(len(profiles_mean['vars']) + len(profiles_mean_multi) + len(time_series['vars']) + len(time_series_multi) + len(contours['vars']) + len(scatters_mean))
num_base_plots = len(time_slices)*(len(profiles_mean['vars']) + len(profiles_mean_multi) + len(time_series['vars']) + len(time_series_multi) + len(scatters_mean))
num_total_plots = 0
if(plot_ind_datasets):
    num_total_plots += len(gmtb_scm_datasets)*num_base_plots
if(len(gmtb_scm_datasets) > 1):
    num_total_plots += num_base_plots #- len(time_slices)*len(contours['vars'])

num_plots_completed = 0


#perform any special checks on the config file data
if len(gmtb_scm_datasets) != len(gmtb_scm_datasets_labels):
    print 'The number of gmtb_scm_datasets must match the number of gmtb_scm_datasets_labels. Quitting...'
    print 'gmtb_scm_datasets = ',gmtb_scm_datasets
    print 'gmtb_scm_datasets_labels = ',gmtb_scm_datasets_labels
    quit()

#read in the case name from the experiment_config namelist (just use first dataset dir namelist)
i = gmtb_scm_datasets[0][:gmtb_scm_datasets[0].rfind('/')].rfind('/') #find the second-to-last index of '/'
dir = gmtb_scm_datasets[0][:i]
for filename in glob.glob(os.path.join(dir, '*.nml')):
    nml = f90nml.read(filename)
    if nml['experiment_config']:
        case_name = nml['experiment_config']['case_name']



#initialize lists for output variables
year = []
month = []
day = []
hour = []
time = []
date = []
pres_l = []
pres_i = []
sigma_l = []
sigma_i = []
phi_l = []
phi_i = []
qv = []
T = []
u = []
v = []
qc = []
qv_force_tend = []
T_force_tend = []
u_force_tend = []
v_force_tend = []
w_ls = []
u_g = []
v_g = []
dT_dt_rad_forc = []
h_advec_thil = []
h_advec_qt = []
T_s = []
pres_s = []
lhf = []
shf = []
tau_u = []
tau_v = []
cld = []
sw_rad_heating_rate = []
lw_rad_heating_rate = []
precip = []
rain = []
rainc = []
pwat = []
dT_dt_lwrad = []
dT_dt_swrad = []
dT_dt_PBL = []
dT_dt_deepconv = []
dT_dt_shalconv = []
dT_dt_micro = []
dT_dt_conv = []
dq_dt_PBL = []
dq_dt_deepconv = []
dq_dt_shalconv = []
dq_dt_micro = []
dq_dt_conv = []
upd_mf = []
dwn_mf = []
det_mf = []
PBL_height = []
sw_up_TOA_tot = []
sw_dn_TOA_tot = []
sw_up_TOA_clr = []
sw_up_sfc_tot = []
sw_dn_sfc_tot = []
sw_up_sfc_clr = []
sw_dn_sfc_clr = []
lw_up_TOA_tot = []
lw_up_TOA_clr = []
lw_up_sfc_tot = []
lw_up_sfc_clr = []
lw_dn_sfc_tot = []
lw_dn_sfc_clr = []
rh = []
rh_500 = []
rad_net_srf = []

time_slice_indices = []
time_slice_labels = []

for i in range(len(gmtb_scm_datasets)):
    nc_fid = Dataset(gmtb_scm_datasets[i], 'r')

    #3D vars have dimensions (time, levels, horizontal)

    year.append(nc_fid.variables['init_year'][:])
    month.append(nc_fid.variables['init_month'][:])
    day.append(nc_fid.variables['init_day'][:])
    hour.append(nc_fid.variables['init_hour'][:])

    time.append(nc_fid.variables['time'][:])
    pres_l.append(nc_fid.variables['pres'][:])
    pres_i.append(nc_fid.variables['pres_i'][:])
    sigma_l.append(nc_fid.variables['sigma'][:])
    sigma_i.append(nc_fid.variables['sigma_i'][:])
    phi_l.append(nc_fid.variables['phi'][:])
    phi_i.append(nc_fid.variables['phi_i'][:])
    qv.append(nc_fid.variables['qv'][:])
    T.append(nc_fid.variables['T'][:])
    u.append(nc_fid.variables['u'][:])
    v.append(nc_fid.variables['v'][:])
    qc.append(nc_fid.variables['qc'][:])
    qv_force_tend.append(nc_fid.variables['qv_force_tend'][:]*86400.0*1.0E3)
    T_force_tend.append(nc_fid.variables['T_force_tend'][:]*86400.0)
    u_force_tend.append(nc_fid.variables['u_force_tend'][:]*86400.0)
    v_force_tend.append(nc_fid.variables['v_force_tend'][:]*86400.0)
    w_ls.append(nc_fid.variables['w_ls'][:])
    u_g.append(nc_fid.variables['u_g'][:])
    v_g.append(nc_fid.variables['v_g'][:])
    dT_dt_rad_forc.append(nc_fid.variables['dT_dt_rad_forc'][:])
    h_advec_thil.append(nc_fid.variables['h_advec_thil'][:])
    h_advec_qt.append(nc_fid.variables['h_advec_qt'][:])
    T_s.append(nc_fid.variables['T_s'][:])
    pres_s.append(nc_fid.variables['pres_s'][:])
    lhf.append(nc_fid.variables['lhf'][:])
    shf.append(nc_fid.variables['shf'][:])
    tau_u.append(nc_fid.variables['tau_u'][:])
    tau_v.append(nc_fid.variables['tau_v'][:])
    cld.append(nc_fid.variables['cldcov'][:])
    sw_rad_heating_rate.append(nc_fid.variables['sw_rad_heating_rate'][:])
    lw_rad_heating_rate.append(nc_fid.variables['lw_rad_heating_rate'][:])
    precip.append(nc_fid.variables['precip'][:]*3600.0) #convert to mm/hr
    rain.append(nc_fid.variables['rain'][:]*1000.0*3600.0) #convert to mm/hr from m/s
    rainc.append(nc_fid.variables['rainc'][:]*1000.0*3600.0) #convert to mm/hr from m/s
    pwat.append(nc_fid.variables['pwat'][:]/(1.0E3)*100.0) #convert to cm
    dT_dt_lwrad.append(nc_fid.variables['dT_dt_lwrad'][:]*86400.0)
    dT_dt_swrad.append(nc_fid.variables['dT_dt_swrad'][:]*86400.0)
    dT_dt_PBL.append(nc_fid.variables['dT_dt_PBL'][:]*86400.0)
    dT_dt_deepconv.append(nc_fid.variables['dT_dt_deepconv'][:]*86400.0)
    dT_dt_shalconv.append(nc_fid.variables['dT_dt_shalconv'][:]*86400.0)
    dT_dt_micro.append(nc_fid.variables['dT_dt_micro'][:]*86400.0)
    dT_dt_conv.append(dT_dt_deepconv[-1] + dT_dt_shalconv[-1])
    dq_dt_PBL.append(nc_fid.variables['dq_dt_PBL'][:]*86400.0*1.0E3)
    dq_dt_deepconv.append(nc_fid.variables['dq_dt_deepconv'][:]*86400.0*1.0E3)
    dq_dt_shalconv.append(nc_fid.variables['dq_dt_shalconv'][:]*86400.0*1.0E3)
    dq_dt_micro.append(nc_fid.variables['dq_dt_micro'][:]*86400.0*1.0E3)
    dq_dt_conv.append(dq_dt_deepconv[-1] + dq_dt_shalconv[-1])
    upd_mf.append(nc_fid.variables['upd_mf'][:])
    dwn_mf.append(nc_fid.variables['dwn_mf'][:])
    det_mf.append(nc_fid.variables['det_mf'][:])
    PBL_height.append(nc_fid.variables['PBL_height'][:])
    sw_up_TOA_tot.append(nc_fid.variables['sw_up_TOA_tot'][:])
    sw_dn_TOA_tot.append(nc_fid.variables['sw_dn_TOA_tot'][:])
    sw_up_TOA_clr.append(nc_fid.variables['sw_up_TOA_clr'][:])
    sw_up_sfc_tot.append(nc_fid.variables['sw_up_sfc_tot'][:])
    sw_dn_sfc_tot.append(nc_fid.variables['sw_dn_sfc_tot'][:])
    sw_up_sfc_clr.append(nc_fid.variables['sw_up_sfc_clr'][:])
    sw_dn_sfc_clr.append(nc_fid.variables['sw_dn_sfc_clr'][:])
    lw_up_TOA_tot.append(nc_fid.variables['lw_up_TOA_tot'][:])
    lw_up_TOA_clr.append(nc_fid.variables['lw_up_TOA_clr'][:])
    lw_up_sfc_tot.append(nc_fid.variables['lw_up_sfc_tot'][:])
    lw_up_sfc_clr.append(nc_fid.variables['lw_up_sfc_clr'][:])
    lw_dn_sfc_tot.append(nc_fid.variables['lw_dn_sfc_tot'][:])
    lw_dn_sfc_clr.append(nc_fid.variables['lw_dn_sfc_clr'][:])
    initial_date = datetime.datetime(year[i][0], month[i][0], day[i][0], hour[i][0], 0, 0, 0)

    #convert times to datetime objects starting from initial date
    date.append(np.array([initial_date + datetime.timedelta(seconds=s) for s in np.int_(time[-1][0])]))

    nc_fid.close()

    #calculate diagnostic values from model output
    e_s = 6.1078*np.exp(17.2693882*(T[-1] - 273.16)/(T[-1] - 35.86))*100.0 #Tetens formula produces e_s in mb (convert to Pa)
    e = qv[-1]*pres_l[-1]/(qv[-1] + (Rd/Rv)*(1.0 - qv[-1])) #compute vapor pressure from specific humidity
    rh.append(np.clip(e/e_s, 0.0, 1.0))

    rh_500_kjl = np.zeros((pres_l[-1].shape[0],pres_l[-1].shape[1],pres_l[-1].shape[3]))
    for l in range(pres_l[-1].shape[0]): #loop over ensemble members
        for j in range(pres_l[-1].shape[1]): #loop over times
            for k in range(pres_l[-1].shape[3]): #loop over hor. index
                index_500 = np.where(pres_l[-1][l,j,:,k]*0.01 < 500.0)[0][0]
                lifrac = (pres_l[-1][l,j,index_500-1,k] - 50000.0)/(pres_l[-1][l,j,index_500-1,k] - pres_l[-1][l,j,index_500,k])
                rh_500_kjl[l,j,k] = rh[-1][l,j,index_500-1,k] + lifrac*(rh[-1][l,j,index_500,k] - rh[-1][l,j,index_500-1,k])
                #print index_500, pres_l[-1][j,index_500,k], pres_l[-1][j,index_500-1,k], rh_500_kj, rh[-1][j,index_500,k], rh[-1][j,index_500-1,k]
    rh_500.append(rh_500_kjl)

    rad_net_srf.append((sw_dn_sfc_tot[-1] - sw_up_sfc_tot[-1]) + (lw_dn_sfc_tot[-1] - lw_up_sfc_tot[-1]))

time_h = [x/3600.0 for x in time]

#find the indices corresponding to the start and end times of the time slices defined in the config file
for time_slice in time_slices:
    time_slice_labels.append(time_slice)
    start_date = datetime.datetime(time_slices[time_slice]['start'][0], time_slices[time_slice]['start'][1],time_slices[time_slice]['start'][2], time_slices[time_slice]['start'][3])
    end_date = datetime.datetime(time_slices[time_slice]['end'][0], time_slices[time_slice]['end'][1],time_slices[time_slice]['end'][2], time_slices[time_slice]['end'][3])
    start_date_index = np.where(date[i] == start_date)[0][0]
    end_date_index = np.where(date[i] == end_date)[0][0]
    time_slice_indices.append([start_date_index, end_date_index])



#fill the obs_dict by calling the appropriate observation file read routine
if(obs_compare and obs_file):
    if(case_name.strip() == 'twpice'):
        obs_dict = gsro.read_twpice_obs(obs_file, time_slices, date)

try:
    os.makedirs(plot_dir)
except OSError:
    if not os.path.isdir(plot_dir):
        raise

if(profiles_mean['vert_axis'] in locals()):
    if(obs_compare):
        obs_vert_axis = np.array(obs_dict[profiles_mean['vert_axis']])
    vert_axis_label_pm = profiles_mean['vert_axis_label']
    y_inverted_val_pm = profiles_mean['y_inverted']
    y_log_val_pm = profiles_mean['y_log']
    y_min_option_pm = profiles_mean['y_min_option']
    y_max_option_pm = profiles_mean['y_max_option']

# if(contours['vert_axis'] in locals()):
#     vert_axis_label_c = contours['vert_axis_label']
#     y_inverted_val_c = contours['y_inverted']
#     y_log_val_c = contours['y_log']
#     y_min_option_c = contours['y_min_option']
#     y_max_option_c = contours['y_max_option']

#make plots for each dataset individually (colors should stay the same for each dataset [using color_index keyword])
if(plot_ind_datasets):
    for i in range(len(gmtb_scm_datasets)):
        #loop through the time slices
        for j in range(len(time_slice_labels)):
            ind_dir = plot_dir + gmtb_scm_datasets_labels[i] + '/' + time_slice_labels[j]

            #make the directory for the current dataset
            try:
                os.makedirs(ind_dir)
            except OSError:
                if not os.path.isdir(ind_dir):
                    raise



            ### Mean Profiles ###

            #check if the specified vertical axis data exists and create the vertical axis for the mean_profile plots
            if(profiles_mean['vert_axis'] in locals()):
                vert_axis_data = np.array(locals()[profiles_mean['vert_axis']][i])
                vert_axis = np.mean(vert_axis_data[:,time_slice_indices[j][0]:time_slice_indices[j][1],:,:], (0,1,3))
                if y_min_option_pm == 'min':
                    y_min_val = np.amin(vert_axis)
                elif (y_min_option_pm == 'max'):
                    y_min_val = np.amax(vert_axis)
                else:
                    y_min_val = profiles_mean['y_min']
                if(y_max_option_pm == 'min'):
                    y_max_val = np.amin(vert_axis)
                elif(y_max_option_pm == 'max'):
                    y_max_val = np.amax(vert_axis)
                else:
                    y_max_val = profiles_mean['y_max']
                y_lim_val = [y_min_val, y_max_val]

                #plot mean profiles
                for k in range(len(profiles_mean['vars'])):
                    #get the python variable associated with the vars listed in the config file
                    if(profiles_mean['vars'][k] in locals()):
                        data = np.array(locals()[profiles_mean['vars'][k]][i])
                        data_time_slice = data[:,time_slice_indices[j][0]:time_slice_indices[j][1],:,:]
                        label = profiles_mean['vars_labels'][k]

                        #mean profile is obtained by averaging over dimensions 1 and 3
                        mean_data = np.mean(data_time_slice, (1,3))

                        #gspr.plot_profile(vert_axis, mean_data, label, vert_axis_label, ind_dir + '/profiles_mean_' + profiles_mean['vars'][k] + '.eps', y_inverted=y_inverted_val, y_log=y_log_val, y_lim=y_lim_val)
                        if(obs_compare and obs_dict.has_key(profiles_mean['vars'][k])):
                            obs_data = np.array(obs_dict[profiles_mean['vars'][k]])
                            obs_data_time_slice = obs_data[obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1],:]

                            obs_mean_data = np.mean(obs_data_time_slice, (0))

                            gspr.plot_profile_multi_ens(vert_axis, [mean_data], [gmtb_scm_datasets_labels[i]], label, vert_axis_label_pm, ind_dir + '/profiles_mean_' + profiles_mean['vars'][k] + '.pdf', y_inverted=y_inverted_val_pm, y_log=y_log_val_pm, y_lim=y_lim_val, obs_z=obs_vert_axis, obs_values=obs_mean_data, line_type='color', color_index=i)

                        else:
                            gspr.plot_profile_multi_ens(vert_axis, [mean_data], [gmtb_scm_datasets_labels[i]], label, vert_axis_label_pm, ind_dir + '/profiles_mean_' + profiles_mean['vars'][k] + '.pdf', y_inverted=y_inverted_val_pm, y_log=y_log_val_pm, y_lim=y_lim_val, line_type='color', color_index=i)

                    else:
                        print 'The variable ' + profiles_mean['vars'][k] + ' found in ' + args.config[0] + ' in the profiles_mean section is invalid.'
                    num_plots_completed += 1
                    print_progress(num_plots_completed, num_total_plots)


                for multiplot in profiles_mean_multi:
                    #multiplot_vars = profiles_mean_multi[multiplot]['vars']

                    #check if all the vars exist
                    all_vars_exist = True
                    for l in range(len(profiles_mean_multi[multiplot]['vars'])):
                        if (profiles_mean_multi[multiplot]['vars'][l] not in locals()):
                            all_vars_exist = False
                            print 'The variable ' + profiles_mean_multi[multiplot]['vars'][l] + ' found in ' + args.config[0] + ' in the ' + multiplot + ' section of profiles_mean_multi is invalid.'

                    if all_vars_exist:
                        data_list = []
                        for l in range(len(profiles_mean_multi[multiplot]['vars'])):
                            data = np.array(locals()[profiles_mean_multi[multiplot]['vars'][l]])
                            data_time_slice = data[i,:,time_slice_indices[j][0]:time_slice_indices[j][1],:,:]
                            data_list.append(np.mean(data_time_slice, (1,3)))

                        gspr.plot_profile_multi_ens(vert_axis, data_list, profiles_mean_multi[multiplot]['vars_labels'], profiles_mean_multi[multiplot]['x_label'], vert_axis_label_pm, ind_dir + '/profiles_mean_multi_' + multiplot + '.pdf', y_inverted=y_inverted_val_pm, y_log=y_log_val_pm, y_lim=y_lim_val, line_type='style', color_index=i)

                    num_plots_completed += 1
                    print_progress(num_plots_completed, num_total_plots)
            else:
                print 'The variable ' + profiles_mean['vert_axis'] + ' found in ' + args.config[0] + ' in the profiles_mean section is invalid.'

            ### Time-Series ###
            for k in range(len(time_series['vars'])):
                if(time_series['vars'][k] in locals()):
                    data = np.array(locals()[time_series['vars'][k]][i])
                    data_time_slice = data[:,time_slice_indices[j][0]:time_slice_indices[j][1]]

                    label = time_series['vars_labels'][k]

                    if(obs_compare and obs_dict.has_key(time_series['vars'][k])):
                        #get the corresponding obs data
                        obs_data = np.array(obs_dict[time_series['vars'][k]])

                        #isolate the subset of the obs data for the current time slice
                        obs_data_time_slice = obs_data[obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]

                        if time_series_resample:
                            #determine whether obs data frequency matches model output frequency
                            data_delta_seconds = time[i][0][time_slice_indices[j][1]] - time[i][0][time_slice_indices[j][1]-1]
                            obs_delta_seconds = obs_dict['time'][obs_dict['time_slice_indices'][j][1]] - obs_dict['time'][obs_dict['time_slice_indices'][j][1]-1]
                            if(obs_delta_seconds > data_delta_seconds):
                                #need to downsample the model data to the obs data frequency

                                #create date range for the model data
                                data_dateoffset = pd.DateOffset(seconds=int(data_delta_seconds))
                                data_time_slice_periods = time_slice_indices[j][1] - time_slice_indices[j][0]
                                data_date_range = pd.date_range(start=date[i][time_slice_indices[j][0]], periods=data_time_slice_periods, freq=data_dateoffset)

                                #create date range for the obs data
                                obs_data_dateoffset = pd.DateOffset(seconds=int(obs_delta_seconds))
                                obs_time_slice_periods = obs_dict['time_slice_indices'][j][1] - obs_dict['time_slice_indices'][j][0]
                                obs_date_range = pd.date_range(start=obs_dict['date'][obs_dict['time_slice_indices'][j][0]], periods=obs_time_slice_periods, freq=obs_data_dateoffset)

                                resample_string = str(int(obs_delta_seconds)) + 'S'
                                data_time_slice_series_rs_ens = []
                                for l in range(data_time_slice.shape[0]):
                                    data_time_slice_series = pd.Series(data_time_slice[l,:,0], index = data_date_range)
                                    data_time_slice_series_rs_ens.append(data_time_slice_series.resample(resample_string, how='mean'))
                                data_time_slice_series_rs_ens = np.array(data_time_slice_series_rs_ens)

                                gspr.plot_time_series_multi_ens(obs_date_range, [data_time_slice_series_rs_ens], [gmtb_scm_datasets_labels[i]], 'date', label, ind_dir + '/time_series_' + time_series['vars'][k] + '.pdf', obs_time = obs_date_range, obs_values = obs_data_time_slice, line_type='color', color_index=i)
                            elif(obs_delta_seconds < data_delta_seconds):
                                print 'The case where observations are more frequent than model output has not been implmented yet... '
                            else:
                                obs_time_time_slice = obs_time_h[obs_time_slice_indices[j][0]:obs_time_slice_indices[j][1]]
                                gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], [data_time_slice], [gmtb_scm_datasets_labels[i]], 'time (h)', label, ind_dir + '/time_series_' + time_series['vars'][k] + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, line_type='color', color_index=i)
                        else:
                            obs_time_time_slice = obs_dict['time_h'][obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                            gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], [data_time_slice], [gmtb_scm_datasets_labels[i]], 'time (h)', label, ind_dir + '/time_series_' + time_series['vars'][k] + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, line_type='color', color_index=i)
                    else:
                        gspr.plot_time_series_multi(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], [data_time_slice], [gmtb_scm_datasets_labels[i]], 'time (h)', label, ind_dir + '/time_series_' + time_series['vars'][k] + '.pdf', line_type='color', color_index=i)
                else:
                    print 'The variable ' + time_series['vars'][k] + ' found in ' + args.config[0] + ' in the time_series section is invalid.'
                num_plots_completed += 1
                print_progress(num_plots_completed, num_total_plots)

            for multiplot in time_series_multi:
                #check if all the vars exist

                all_vars_exist = True
                for l in range(len(time_series_multi[multiplot]['vars'])):
                    if (time_series_multi[multiplot]['vars'][l] not in locals()):
                        all_vars_exist = False
                        print 'The variable ' + time_series_multi[multiplot]['vars'][l] + ' found in ' + args.config[0] + ' in the ' + multiplot + ' section of time_series_multi is invalid.'

                if all_vars_exist:
                    data_list = []
                    for l in range(len(time_series_multi[multiplot]['vars'])):

                        data = np.array(locals()[time_series_multi[multiplot]['vars'][l]][i])
                        data_time_slice = data[:,time_slice_indices[j][0]:time_slice_indices[j][1]]
                        data_list.append(data_time_slice)

                    if(obs_compare and obs_dict.has_key(time_series_multi[multiplot]['obs_var'])):
                        #get the corresponding obs data
                        obs_data = np.array(obs_dict[time_series_multi[multiplot]['obs_var']])

                        #isolate the subset of the obs data for the current time slice
                        obs_data_time_slice = obs_data[obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                        if time_series_resample:
                            #determine whether obs data frequency matches model output frequency
                            data_delta_seconds = time[i][0][time_slice_indices[j][1]] - time[i][0][time_slice_indices[j][1]-1]
                            obs_delta_seconds = obs_dict['time'][obs_dict['time_slice_indices'][j][1]] - obs_dict['time'][obs_dict['time_slice_indices'][j][1]-1]
                            if(obs_delta_seconds > data_delta_seconds):
                                #need to downsample the model data to the obs data frequency

                                #create date range for the model data
                                data_dateoffset = pd.DateOffset(seconds=int(data_delta_seconds))
                                data_time_slice_periods = time_slice_indices[j][1] - time_slice_indices[j][0]
                                data_date_range = pd.date_range(start=date[i][time_slice_indices[j][0]], periods=data_time_slice_periods, freq=data_dateoffset)

                                #create date range for the obs data
                                obs_data_dateoffset = pd.DateOffset(seconds=int(obs_delta_seconds))
                                obs_time_slice_periods = obs_dict['time_slice_indices'][j][1] - obs_dict['time_slice_indices'][j][0]
                                obs_date_range = pd.date_range(start=obs_dict['date'][obs_dict['time_slice_indices'][j][0]], periods=obs_time_slice_periods, freq=obs_data_dateoffset)

                                resample_string = str(int(obs_delta_seconds)) + 'S'
                                data_list_rs = []
                                for l in range(len(data_list)):
                                    dummy_list = []
                                    for m in range(data_list[l].shape[0]):
                                        data_time_slice_series = pd.Series(data_list[l][m,:,0], index = data_date_range)
                                        dummy_list.append(data_time_slice_series.resample(resample_string, how='mean'))
                                    data_list_rs.append(dummy_list)
                                data_list_rs = np.array(data_list_rs)

                                gspr.plot_time_series_multi_ens(obs_date_range, data_list_rs, time_series_multi[multiplot]['vars_labels'], 'date', time_series_multi[multiplot]['y_label'], ind_dir + '/time_series_multi_' + multiplot + '.pdf', obs_time = obs_date_range, obs_values = obs_data_time_slice, obs_label = time_series_multi[multiplot]['obs_var_label'], line_type='style', color_index=i)
                            elif(obs_delta_seconds < data_delta_seconds):
                                print 'The case where observations are more frequent than model output has not been implmented yet... '
                            else:
                                obs_time_time_slice = obs_time_h[obs_time_slice_indices[j][0]:obs_time_slice_indices[j][1]]
                                gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], data_list, time_series_multi[multiplot]['vars_labels'], 'time (h)', time_series_multi[multiplot]['y_label'], ind_dir + '/time_series_multi_' + multiplot + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, obs_label = time_series_multi[multiplot]['obs_var_label'], line_type='style', color_index=i)
                        else:
                            obs_time_time_slice = obs_dict['time_h'][obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                            gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], data_list, time_series_multi[multiplot]['vars_labels'], 'time (h)', time_series_multi[multiplot]['y_label'], ind_dir + '/time_series_multi_' + multiplot + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, obs_label = time_series_multi[multiplot]['obs_var_label'], line_type='style', color_index=i)
                    else:
                        gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], data_list, time_series_multi[multiplot]['vars_labels'], 'time (h)', time_series_multi[multiplot]['y_label'], ind_dir + '/time_series_multi_' + multiplot + '.pdf', line_type='style', color_index=i)

                num_plots_completed += 1
                print_progress(num_plots_completed, num_total_plots)

            # ### Contour Plots ###
            # x_ticks_num = contours['x_ticks_num']
            # x_ticks_val = [time_h[i][time_slice_indices[j][0]], time_h[i][time_slice_indices[j][1]], x_ticks_num]
            # y_ticks_num = contours['y_ticks_num']
            #
            # if(contours['vert_axis'] in locals()):
            #     vert_axis_data = np.array(locals()[contours['vert_axis']][i])
            #     vert_axis = np.mean(vert_axis_data[time_slice_indices[j][0]:time_slice_indices[j][1],:,:], (0,2))
            #     if y_min_option_c == 'min':
            #         y_min_val = np.amin(vert_axis)
            #     elif (y_min_option_c == 'max'):
            #         y_min_val = np.amax(vert_axis)
            #     else:
            #         y_min_val = contours['y_min']
            #     if(y_max_option_c == 'min'):
            #         y_max_val = np.amin(vert_axis)
            #     elif(y_max_option_c == 'max'):
            #         y_max_val = np.amax(vert_axis)
            #     else:
            #         y_max_val = contours['y_max']
            #     y_lim_val = [y_min_val, y_max_val]
            #
            #     vert_axis_top_index = vert_axis.size - bisect.bisect_left(vert_axis[::-1], y_min_val)
            #     y_ticks_val = [y_min_val, y_max_val, y_ticks_num]
            #
            #     for k in range(len(contours['vars'])):
            #         if(contours['vars'][k] in locals()):
            #             data = np.array(locals()[contours['vars'][k]][i])
            #             data_time_slice = data[time_slice_indices[j][0]:time_slice_indices[j][1],:,:]
            #             label = contours['vars_labels'][k]
            #
            #             gspr.contour_plot_firl(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], vert_axis, np.transpose(data_time_slice[:,:,0]), np.amin(data_time_slice[:,0:vert_axis_top_index,0]), np.amax(data_time_slice[:,0:vert_axis_top_index,0]), label, 'time (h)', vert_axis_label_c, ind_dir + '/contour_' + contours['vars'][k] + '.eps', xticks=x_ticks_val, yticks=y_ticks_val, y_inverted=y_inverted_val_c, y_log = y_log_val_c, y_lim = y_lim_val)
            #         else:
            #             print 'The variable ' + contours['vars'][k] + ' found in ' + args.config[0] + ' in the contours section is invalid.'
            #
            #         num_plots_completed += 1
            #         print_progress(num_plots_completed, num_total_plots)
            # else:
            #     print 'The variable ' + contours['vert_axis'] + ' found in ' + args.config[0] + ' in the contours section is invalid.'

            ### Scatter Plots ###
            for scatter_plot in scatters_mean:
                x_data = np.array(locals()[scatters_mean[scatter_plot]['x_var']][i])
                y_data = np.array(locals()[scatters_mean[scatter_plot]['y_var']][i])

                x_data_time_slice = x_data[:,time_slice_indices[j][0]:time_slice_indices[j][1]]
                y_data_time_slice = y_data[:,time_slice_indices[j][0]:time_slice_indices[j][1]]

                x_mean_data = np.mean(x_data_time_slice, axis=(1,2))
                y_mean_data = np.mean(y_data_time_slice, axis=(1,2))
                if scatters_mean[scatter_plot]['ratio']:
                    y_mean_data = y_mean_data/x_mean_data

                x_min_option_sp = scatters_mean[scatter_plot]['x_min_option']
                x_max_option_sp = scatters_mean[scatter_plot]['x_max_option']
                y_min_option_sp = scatters_mean[scatter_plot]['y_min_option']
                y_max_option_sp = scatters_mean[scatter_plot]['y_max_option']

                if x_min_option_sp == 'min':
                    x_min_val = np.amin(x_mean_data)
                else:
                    x_min_val = scatters_mean[scatter_plot]['x_min']
                if(x_max_option_sp == 'max'):
                    x_max_val = np.amax(x_mean_data)
                else:
                    x_max_val = scatters_mean[scatter_plot]['x_max']
                x_lim_val = [x_min_val, x_max_val]
                if y_min_option_sp == 'min':
                    y_min_val = np.amin(y_mean_data)
                else:
                    y_min_val = scatters_mean[scatter_plot]['y_min']
                if(y_max_option_sp == 'max'):
                    y_max_val = np.amax(y_mean_data)
                else:
                    y_max_val = scatters_mean[scatter_plot]['y_max']
                y_lim_val = [y_min_val, y_max_val]

                gspr.plot_scatter_multi([x_mean_data], [y_mean_data], scatters_mean[scatter_plot]['x_label'], scatters_mean[scatter_plot]['y_label'], ind_dir + '/scatter_mean_' + scatter_plot + '.pdf', x_lim = x_lim_val, y_lim = y_lim_val, color_index=i)

                num_plots_completed += 1
                print_progress(num_plots_completed, num_total_plots)

#make comparison plots
if(len(gmtb_scm_datasets) > 1):
    #loop through the time slices
    for j in range(len(time_slice_labels)):
        comp_dir = plot_dir + 'comp/' + time_slice_labels[j]

        #make the directory for the current dataset
        try:
            os.makedirs(comp_dir)
        except OSError:
            if not os.path.isdir(comp_dir):
                raise

        #check if the specified vertical axis data exists and create the vertical axis for the mean_profile plots
        if(profiles_mean['vert_axis'] in locals()):
            vert_axis_data = np.array(locals()[profiles_mean['vert_axis']][0])
            vert_axis = np.mean(vert_axis_data[:,time_slice_indices[j][0]:time_slice_indices[j][1],:,:], (0,1,3))
            if y_min_option_pm == 'min':
                y_min_val = np.amin(vert_axis)
            elif (y_min_option_pm == 'max'):
                y_min_val = np.amax(vert_axis)
            else:
                y_min_val = profiles_mean['y_min']
            if(y_max_option_pm == 'min'):
                y_max_val = np.amin(vert_axis)
            elif(y_max_option_pm == 'max'):
                y_max_val = np.amax(vert_axis)
            else:
                y_max_val = profiles_mean['y_max']
            y_lim_val = [y_min_val, y_max_val]

            #plot mean profiles
            for k in range(len(profiles_mean['vars'])):
                #get the python variable associated with the vars listed in the config file
                if(profiles_mean['vars'][k] in locals()):
                    data = np.array(locals()[profiles_mean['vars'][k]])
                    data_time_slice = data[:,:,time_slice_indices[j][0]:time_slice_indices[j][1],:,:]
                    label = profiles_mean['vars_labels'][k]

                    #mean profile is obtained by averaging over dimensions 0 and 2
                    mean_data = []
                    for i in range(len(gmtb_scm_datasets)):
                        mean_data.append(np.mean(data_time_slice[i,:,:,:,:], (1,3)))

                    if(obs_compare and obs_dict.has_key(profiles_mean['vars'][k])):
                        obs_data = np.array(obs_dict[profiles_mean['vars'][k]])
                        obs_data_time_slice = obs_data[obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1],:]

                        obs_mean_data = np.mean(obs_data_time_slice, (0))

                        gspr.plot_profile_multi_ens(vert_axis, mean_data, gmtb_scm_datasets_labels, label, vert_axis_label_pm, comp_dir + '/profiles_mean_' + profiles_mean['vars'][k] + '.pdf', y_inverted=y_inverted_val_pm, y_log=y_log_val_pm, y_lim=y_lim_val, obs_z=obs_vert_axis, obs_values=obs_mean_data, line_type='color',skill_scores=skill_scores_val)

                    else:
                        gspr.plot_profile_multi_ens(vert_axis, mean_data, gmtb_scm_datasets_labels, label, vert_axis_label_pm, comp_dir + '/profiles_mean_' + profiles_mean['vars'][k] + '.pdf', y_inverted=y_inverted_val_pm, y_log=y_log_val_pm, y_lim=y_lim_val, line_type='color',skill_scores=skill_scores_val)
                else:
                    print 'The variable ' + profiles_mean['vars'][k] + ' found in ' + args.config[0] + ' in the profiles_mean section is invalid.'
                num_plots_completed += 1
                print_progress(num_plots_completed, num_total_plots)

            for multiplot in profiles_mean_multi:
                #multiplot_vars = profiles_mean_multi[multiplot]['vars']

                #check if all the vars exist
                all_vars_exist = True
                for l in range(len(profiles_mean_multi[multiplot]['vars'])):
                    if (profiles_mean_multi[multiplot]['vars'][l] not in locals()):
                        all_vars_exist = False
                        print 'The variable ' + profiles_mean_multi[multiplot]['vars'][l] + ' found in ' + args.config[0] + ' in the ' + multiplot + ' section of profiles_mean_multi is invalid.'

                if all_vars_exist:
                    data_list_of_list = []
                    for l in range(len(profiles_mean_multi[multiplot]['vars'])):
                        data = np.array(locals()[profiles_mean_multi[multiplot]['vars'][l]])
                        data_list = []
                        for i in range(len(gmtb_scm_datasets)):
                            data_time_slice = data[i,:,time_slice_indices[j][0]:time_slice_indices[j][1],:,:]
                            data_list.append(np.mean(data_time_slice, (1,3)))
                        data_list_of_list.append(data_list)

                    gspr.plot_profile_multi_ens(vert_axis, data_list_of_list, [profiles_mean_multi[multiplot]['vars_labels'],gmtb_scm_datasets_labels], profiles_mean_multi[multiplot]['x_label'], vert_axis_label_pm, comp_dir + '/profiles_mean_multi_' + multiplot + '.pdf', y_inverted=y_inverted_val_pm, y_log=y_log_val_pm, y_lim=y_lim_val)

                num_plots_completed += 1
                print_progress(num_plots_completed, num_total_plots)
        else:
            print 'The variable ' + profiles_mean['vert_axis'] + ' found in ' + args.config[0] + ' in the profiles_mean section is invalid.'

        ### Time-Series ###
        for k in range(len(time_series['vars'])):
            if(time_series['vars'][k] in locals()):
                data = np.array(locals()[time_series['vars'][k]])
                data_time_slice = data[:,:,time_slice_indices[j][0]:time_slice_indices[j][1],:]

                label = time_series['vars_labels'][k]

                if(obs_compare and obs_dict.has_key(time_series['vars'][k])):
                    #get the corresponding obs data
                    obs_data = np.array(obs_dict[time_series['vars'][k]])

                    #isolate the subset of the obs data for the current time slice
                    obs_data_time_slice = obs_data[obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]

                    if time_series_resample:
                        #determine whether obs data frequency matches model output frequency
                        data_delta_seconds = time[0][0][time_slice_indices[j][1]] - time[0][0][time_slice_indices[j][1]-1]
                        obs_delta_seconds = obs_dict['time'][obs_dict['time_slice_indices'][j][1]] - obs_dict['time'][obs_dict['time_slice_indices'][j][1]-1]
                        if(obs_delta_seconds > data_delta_seconds):
                            #need to downsample the model data to the obs data frequency

                            #create date range for the model data
                            data_dateoffset = pd.DateOffset(seconds=int(data_delta_seconds))
                            data_time_slice_periods = time_slice_indices[j][1] - time_slice_indices[j][0]
                            data_date_range = pd.date_range(start=date[0][time_slice_indices[j][0]], periods=data_time_slice_periods, freq=data_dateoffset) #assumes dates for all model datasets are the same

                            #create date range for the obs data
                            obs_data_dateoffset = pd.DateOffset(seconds=int(obs_delta_seconds))
                            obs_time_slice_periods = obs_dict['time_slice_indices'][j][1] - obs_dict['time_slice_indices'][j][0]
                            obs_date_range = pd.date_range(start=obs_dict['date'][obs_dict['time_slice_indices'][j][0]], periods=obs_time_slice_periods, freq=obs_data_dateoffset)

                            resample_string = str(int(obs_delta_seconds)) + 'S'

                            #build list of resampled model datasets for this time slice
                            data_time_slice_series_rs = []
                            for i in range(len(gmtb_scm_datasets)):
                                dummy_list =[]
                                for l in range(data_time_slice.shape[1]):
                                    data_time_slice_series = pd.Series(data_time_slice[i,l,:,0], index = data_date_range)
                                    dummy_list.append(data_time_slice_series.resample(resample_string, how='mean'))
                                data_time_slice_series_rs.append(np.array(dummy_list))


                            gspr.plot_time_series_multi_ens(obs_date_range, data_time_slice_series_rs, gmtb_scm_datasets_labels, 'date', label, comp_dir + '/time_series_' + time_series['vars'][k] + '.pdf', obs_time = obs_date_range, obs_values = obs_data_time_slice, line_type='color',skill_scores=skill_scores_val)
                        elif(obs_delta_seconds < data_delta_seconds):
                            print 'The case where observations are more frequent than model output has not been implmented yet... '
                        else:
                            obs_time_time_slice = obs_dict['time_h'][obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                            gspr.plot_time_series_multi_ens(time_h[0][time_slice_indices[j][0]:time_slice_indices[j][1]], data_time_slice, gmtb_scm_datasets_labels, 'time (h)', label, comp_dir + '/time_series_' + time_series['vars'][k] + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, line_type='color',skill_scores=skill_scores_val)
                    else:
                        obs_time_time_slice = obs_dict['time_h'][obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                        gspr.plot_time_series_multi_ens(time_h[0][time_slice_indices[j][0]:time_slice_indices[j][1]], data_time_slice, gmtb_scm_datasets_labels, 'time (h)', label, comp_dir + '/time_series_' + time_series['vars'][k] + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, line_type='color',skill_scores=skill_scores_val)
                else:
                    gspr.plot_time_series_multi_ens(time_h[0][time_slice_indices[j][0]:time_slice_indices[j][1]], data_time_slice, gmtb_scm_datasets_labels, 'time (h)', label, comp_dir + '/time_series_' + time_series['vars'][k] + '.pdf', line_type='color',skill_scores=skill_scores_val)
            else:
                print 'The variable ' + time_series['vars'][k] + ' found in ' + args.config[0] + ' in the time_series section is invalid.'
            num_plots_completed += 1
            print_progress(num_plots_completed, num_total_plots)

        for multiplot in time_series_multi:
            #check if all the vars exist

            all_vars_exist = True
            for l in range(len(time_series_multi[multiplot]['vars'])):
                if (time_series_multi[multiplot]['vars'][l] not in locals()):
                    all_vars_exist = False
                    print 'The variable ' + time_series_multi[multiplot]['vars'][l] + ' found in ' + args.config[0] + ' in the ' + multiplot + ' section of time_series_multi is invalid.'

            if all_vars_exist:
                data_list_of_list = []
                for l in range(len(time_series_multi[multiplot]['vars'])):
                    data = np.array(locals()[time_series_multi[multiplot]['vars'][l]])
                    data_list = []
                    for i in range(len(gmtb_scm_datasets)):
                         data_time_slice = data[i,:,time_slice_indices[j][0]:time_slice_indices[j][1]]
                         data_list.append(data_time_slice)
                    data_list_of_list.append(data_list)

                if(obs_compare and obs_dict.has_key(time_series_multi[multiplot]['obs_var'])):
                    #get the corresponding obs data
                    obs_data = np.array(obs_dict[time_series_multi[multiplot]['obs_var']])

                    #isolate the subset of the obs data for the current time slice
                    obs_data_time_slice = obs_data[obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                    if time_series_resample:
                        #determine whether obs data frequency matches model output frequency
                        data_delta_seconds = time[i][0][time_slice_indices[j][1]] - time[i][0][time_slice_indices[j][1]-1]
                        obs_delta_seconds = obs_dict['time'][obs_dict['time_slice_indices'][j][1]] - obs_dict['time'][obs_dict['time_slice_indices'][j][1]-1]
                        if(obs_delta_seconds > data_delta_seconds):
                            #need to downsample the model data to the obs data frequency

                            #create date range for the model data
                            data_dateoffset = pd.DateOffset(seconds=int(data_delta_seconds))
                            data_time_slice_periods = time_slice_indices[j][1] - time_slice_indices[j][0]
                            data_date_range = pd.date_range(start=date[0][time_slice_indices[j][0]], periods=data_time_slice_periods, freq=data_dateoffset)

                            #create date range for the obs data
                            obs_data_dateoffset = pd.DateOffset(seconds=int(obs_delta_seconds))
                            obs_time_slice_periods = obs_dict['time_slice_indices'][j][1] - obs_dict['time_slice_indices'][j][0]
                            obs_date_range = pd.date_range(start=obs_dict['date'][obs_dict['time_slice_indices'][j][0]], periods=obs_time_slice_periods, freq=obs_data_dateoffset)

                            resample_string = str(int(obs_delta_seconds)) + 'S'
                            data_list_of_list_rs = []
                            for l in range(len(data_list_of_list)):
                                data_list_rs = []
                                for i in range(len(gmtb_scm_datasets)):
                                    dummy_list = []
                                    for m in range(data_list_of_list[l][i].shape[0]):
                                        data_time_slice_series = pd.Series(data_list_of_list[l][i][m,:,0], index = data_date_range)
                                        data_time_slice_series_rs = data_time_slice_series.resample(resample_string, how='mean')
                                        dummy_list.append(data_time_slice_series_rs)
                                    data_list_rs.append(np.array(dummy_list))
                                data_list_of_list_rs.append(data_list_rs)

                            gspr.plot_time_series_multi_ens(obs_date_range, data_list_of_list_rs, [time_series_multi[multiplot]['vars_labels'],gmtb_scm_datasets_labels], 'date', time_series_multi[multiplot]['y_label'], comp_dir + '/time_series_multi_' + multiplot + '.pdf')#, obs_time = obs_date_range, obs_values = obs_data_time_slice, obs_label = time_series_multi[multiplot]['obs_var_label'])
                        elif(obs_delta_seconds < data_delta_seconds):
                            print 'The case where observations are more frequent than model output has not been implmented yet... '
                        else:
                            obs_time_time_slice = obs_time_h[obs_time_slice_indices[j][0]:obs_time_slice_indices[j][1]]
                            gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], data_list_of_list, [time_series_multi[multiplot]['vars_labels'],gmtb_scm_datasets_labels], 'time (h)', time_series_multi[multiplot]['y_label'], comp_dir + '/time_series_multi_' + multiplot + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, obs_label = time_series_multi[multiplot]['obs_var_label'])
                    else:
                        obs_time_time_slice = obs_dict['time_h'][obs_dict['time_slice_indices'][j][0]:obs_dict['time_slice_indices'][j][1]]
                        gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], data_list_of_list, [time_series_multi[multiplot]['vars_labels'],gmtb_scm_datasets_labels], 'time (h)', time_series_multi[multiplot]['y_label'], comp_dir + '/time_series_multi_' + multiplot + '.pdf', obs_time = obs_time_time_slice, obs_values = obs_data_time_slice, obs_label = time_series_multi[multiplot]['obs_var_label'])
                else:
                    gspr.plot_time_series_multi_ens(time_h[i][time_slice_indices[j][0]:time_slice_indices[j][1]], data_list_of_list, [time_series_multi[multiplot]['vars_labels'],gmtb_scm_datasets_labels], 'time (h)', time_series_multi[multiplot]['y_label'], comp_dir + '/time_series_multi_' + multiplot + '.pdf')

            num_plots_completed += 1
            print_progress(num_plots_completed, num_total_plots)

            ### Scatter Plots ###
            for scatter_plot in scatters_mean:
                x_data = np.array(locals()[scatters_mean[scatter_plot]['x_var']])
                y_data = np.array(locals()[scatters_mean[scatter_plot]['y_var']])

                x_data_time_slice = x_data[:,:,time_slice_indices[j][0]:time_slice_indices[j][1]]
                y_data_time_slice = y_data[:,:,time_slice_indices[j][0]:time_slice_indices[j][1]]

                x_mean_data = []
                y_mean_data = []
                for i in range(len(gmtb_scm_datasets)):
                    x_mean_data.append(np.mean(x_data_time_slice[i], axis=(1,2)))
                    y_mean_data.append(np.mean(y_data_time_slice[i], axis=(1,2)))
                    if scatters_mean[scatter_plot]['ratio']:
                        y_mean_data[i] = y_mean_data[i]/x_mean_data[i]

                x_min_option_sp = scatters_mean[scatter_plot]['x_min_option']
                x_max_option_sp = scatters_mean[scatter_plot]['x_max_option']
                y_min_option_sp = scatters_mean[scatter_plot]['y_min_option']
                y_max_option_sp = scatters_mean[scatter_plot]['y_max_option']

                if x_min_option_sp == 'min':
                    x_min_val = np.amin(x_mean_data)
                else:
                    x_min_val = scatters_mean[scatter_plot]['x_min']
                if(x_max_option_sp == 'max'):
                    x_max_val = np.amax(x_mean_data)
                else:
                    x_max_val = scatters_mean[scatter_plot]['x_max']
                x_lim_val = [x_min_val, x_max_val]
                if y_min_option_sp == 'min':
                    y_min_val = np.amin(y_mean_data)
                else:
                    y_min_val = scatters_mean[scatter_plot]['y_min']
                if(y_max_option_sp == 'max'):
                    y_max_val = np.amax(y_mean_data)
                else:
                    y_max_val = scatters_mean[scatter_plot]['y_max']
                y_lim_val = [y_min_val, y_max_val]

                gspr.plot_scatter_multi(x_mean_data, y_mean_data, scatters_mean[scatter_plot]['x_label'], scatters_mean[scatter_plot]['y_label'], comp_dir + '/scatter_mean_' + scatter_plot + '.pdf', x_lim = x_lim_val, y_lim = y_lim_val)

                num_plots_completed += 1
                print_progress(num_plots_completed, num_total_plots)
