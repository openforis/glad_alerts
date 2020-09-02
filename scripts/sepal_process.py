import time
import subprocess
import glob
import os
import ee
import sys
sys.path.append("..") # Adds higher directory to python modules path
from utils import utils
from scripts import gdrive
from threading import Thread
import ipyvuetify as v
from sepal_ui.scripts import utils as su
from sepal_ui import widgetFactory as wf
from utils import messages as ms
from scripts import gee_process
from utils import parameters as pm
from sepal_ui.scripts import mapping
import numpy as np
from bqplot import *
import matplotlib.pyplot as plt
import csv
from sepal_ui import oft 
from sepal_ui import gdal as sgdal
import gdal
import pandas as pd

#initialize earth engine
ee.Initialize()

def download_task_tif(filename, glad_dir):
    """Download the tif files from your google drive folder to the local glad_results folder
    
    Args:
        filename (str): pathname pattern to the .tif files
        glad_dir (str): pathname to the local gad_result directory
    """
    drive_handler = gdrive.gdrive()
    files = drive_handler.get_files(filename)
    drive_handler.download_files(files, glad_dir)
    
def delete_local_file(pathname):
    """delete the files that have been already merged
    
    Args:
        pathnamec (str): the pathname patern to the .tif files 
        
    Returns: 
        (str): a message corresponding to the number of deleted files
    """
    #list the input files
    file_list = []
    for file in glob.glob(pathname):
        file_list.append(file)
        
    count = 0
    for file in file_list:
        os.remove(file)
        count += 1
        
    return "{0} files deleted".format(count)


def sepal_process(asset_name, year, date_range, output, oft_output):
    """execute the 3 different operations of the computation successively: merge, clump and compute
    
    Args:
        asset_name (str): the assetId of the aoi computed in step 1
        year (str): the year used to compute the glad alerts
        widget_alert (v.Alert) the alert that display the output of the process
        
    Returns:
        (str,str): the links to the .tif (res. .txt) file 
    """
    
    output_debug = [v.Html(tag="h3", children=['Process outputs'])]
    
    aoi_name= utils.get_aoi_name(asset_name)
        
    #define the files variables
    glad_dir = utils.create_result_folder(asset_name)
    
    #year and country_code are defined by step 1 cell
    basename = glad_dir + aoi_name + '_' + date_range[0] + '_' + date_range[1]  
    alert_date_tmp_map = basename + '_tmp_glad_date.tif'
    alert_date_map     = basename + '_glad_date.tif'
    alert_tmp_map      = basename + '_tmp_glad.tif'
    alert_map          = basename + '_glad.tif'
    clump_tmp_map      = basename + '_tmp_clump.tif'
    clump_map          = basename + '_clump.tif'
    alert_stats        = basename + '_stats.txt'
        
    filename = utils.construct_filename(asset_name, date_range)
    
    #check that the tiles exist in gdrive
    drive_handler = gdrive.gdrive()
    files = drive_handler.get_files(filename)
    
    if files == []:
        su.displayIO(output, ms.NO_TASK, 'error')
        return (None, None)
        
    #check that the process is not already done
    if utils.check_for_file(alert_stats):
        su.displayIO(output, ms.ALREADY_DONE, 'success')
        return (alert_map, alert_stats)
    
    ##############################
    ##   digest the date map    ##
    ##############################
    filename_date = filename + '_date'
    download_task_tif(filename_date, glad_dir)
    
    pathname = filename_date + "*.tif"
    
    files = []
    for file in glob.glob(glad_dir + pathname):
        files.append(file)
        
    #run the merge process
    su.displayIO(output, ms.MERGE_TILE)
    time.sleep(2)
    io = sgdal.merge(files, out_filename=alert_date_tmp_map, v=True, output=oft_output)
    output_debug.append(v.Html(tag='p', children=[io]))
    
    #delete local files
    for file in files:
        os.remove(file)
    
    #compress raster
    su.displayIO(output, ms.COMPRESS_FILE)
    gdal.Translate(alert_date_map, alert_date_tmp_map, creationOptions=['COMPRESS=LZW'])
    os.remove(alert_date_tmp_map)
    
    ##############################
    ##   digest the map         ##
    ##############################
    
    #download from GEE
    filename_map = filename + '_map'
    download_task_tif(filename_map, glad_dir)
        
    #process data with otf
    pathname = filename_map + "*.tif"
    
    #create the files list 
    files = []
    for file in glob.glob(glad_dir + pathname):
        files.append(file)
    
    #run the merge process
    su.displayIO(output, ms.MERGE_TILE)
    time.sleep(2)
    io = sgdal.merge(files, out_filename=alert_tmp_map, v=True, output=oft_output)
    output_debug.append(v.Html(tag='p', children=[io]))
    
    #delete local files
    for file in files:
        os.remove(file)
    
    #compress raster
    su.displayIO(output, ms.COMPRESS_FILE)
    gdal.Translate(alert_map, alert_tmp_map, creationOptions=['COMPRESS=LZW'])
    os.remove(alert_tmp_map)
    
    #clump the patches together
    su.displayIO(output, ms.IDENTIFY_PATCH)
    time.sleep(2)
    io = oft.clump(alert_map, clump_tmp_map, output=oft_output)
    output_debug.append(v.Html(tag='p', children=[io]))
    
    #compress clump raster
    su.displayIO(output, ms.COMPRESS_FILE)
    gdal.Translate(clump_map, clump_tmp_map, creationOptions=['COMPRESS=LZW'])
    os.remove(clump_tmp_map)
    
    #create the histogram of the patches
    su.displayIO(output, ms.PATCH_SIZE)
    time.sleep(2)
    io = oft.his(alert_map, alert_stats, maskfile=clump_map, maxval=3, output=oft_output)
    output_debug.append(v.Html(tag='p', children=[io]))
    
    su.displayIO(output, ms.COMPUTAION_COMPLETED, 'success')  
    
    oft_output.children = output_debug
    
    return (alert_map, alert_stats)

def display_results(asset_name, year, date_range, raster):
    
    glad_dir = utils.create_result_folder(asset_name)
    aoi_name = utils.get_aoi_name(asset_name) 
    
    basename = glad_dir + aoi_name + '_' + date_range[0] + '_' + date_range[1]
    alert_stats = basename + '_stats.txt'
    
    df = pd.read_csv(alert_stats, header=None, sep=' ') 
    df.columns = ['patchId', 'nb_pixel', 'no_data', 'no_alerts', 'prob', 'conf']
    
    ####################
    ##     tif link   ##
    ####################
    tif_btn = wf.DownloadBtn(ms.TIF_BTN, raster)
    
    ####################
    ##    csv file    ##
    ####################
    
    alert_csv = create_csv(df, aoi_name, glad_dir, date_range)
    csv_btn = wf.DownloadBtn(ms.CSV_BTN, alert_csv)
    
    ##########################
    ##    create the figs   ##
    ##########################
    
    figs = []
    
    bins=30
    
    x_sc = LinearScale(min=1)
    y_sc = LinearScale()
    
    ax_x = Axis(label='patch size (px)', scale=x_sc)
    ax_y = Axis(label='number of pixels', scale=y_sc, orientation='vertical') 
    
    colors = pm.getPalette()

    #load the confirm patches
    y_conf = df[df['conf'] != 0]['conf'].to_numpy()
    y_conf = np.append(y_conf, 0) #add the 0 to prevent bugs when there are no data (2017 for ex)
    max_conf = np.amax(y_conf)
    
    #cannot plot 2 bars charts with different x_data
    conf_y, conf_x = np.histogram(y_conf, bins=30, weights=y_conf)
    bar = Bars(x=conf_x, y=conf_y, scales={'x': x_sc, 'y': y_sc}, colors=[colors[0]])
    title ='Distribution of the confirmed GLAD alerts for {0} in {1}'.format(aoi_name, year)
    
    figs.append(Figure(
        title= title,
        marks=[bar], 
        axes=[ax_x, ax_y] 
    ))
    
    #load the prob patches
    y_prob = df[df['prob'] != 0]['prob'].to_numpy()
    y_prob = np.append(y_prob, 0) #add the 0 to prevent bugs when there are no data (2017 for ex)
    max_prob = np.amax(y_prob)
    
    #cannot plot 2 bars charts with different x_data
    prob_y, prob_x = np.histogram(y_prob, bins=30, weights=y_prob)
    bar = Bars(x=prob_x, y=prob_y, scales={'x': x_sc, 'y': y_sc}, colors=[colors[1]])
    title ='Distribution of the potential GLAD alerts for {0} in {1}'.format(aoi_name, year)
    
    figs.append(Figure(
        title= title,
        marks=[bar], 
        axes=[ax_x, ax_y]
    ))
    
    ##########################################
    #       clean display when no probale    #
    ##########################################
    labels = ['confirmed alert', 'potential alert']
    data_hist = [y_conf, y_prob]
    if not year == pm.getLastUpdatedYear():
        labels = [labels[0]]
        data_hist = [data_hist[0]]
        figs = [figs[0]]
        colors = [colors[0]]
    
    ############################
    ##       create hist      ##
    ############################
    
    png_link = basename + '_hist.png'
    
    title = 'Distribution of the GLAD alerts \nfor {0} in {1}'.format(aoi_name, year)
    png_link = create_png(
        data_hist, 
        labels, 
        colors, 
        bins, 
        max(max_conf,max_prob), 
        title, 
        png_link
    )
    png_btn = wf.DownloadBtn(ms.PNG_BTN, png_link)
    
    ###########################
    ##      create the map   ##
    ###########################
    m = display_alerts(asset_name, year, date_range)
    
    #########################
    ##   sum-up layout     ##
    #########################
    
    #create the partial layout 
    partial_layout = v.Layout(
        Row=True,
        align_center=True,
        class_='pa-0 mt-5', 
        children=[
            v.Flex(xs12=True, md6=True, class_='pa-0', children=figs),
            v.Flex(xs12=True, md6=True, class_='pa-0', children=[m])
        ]
    )
    
    #create the display
    children = [ 
        v.Layout(Row=True, children=[
            csv_btn,
            png_btn,
            tif_btn
        ]),
        partial_layout
    ]
    
    
    return children

def create_png(data_hist, labels, colors, bins, max_, title, filepath):
    """useless function that create a matplotlib file because bqplot cannot yet export without a popup
    """
    plt.hist(
        data_hist, 
        label=labels, 
        weights=data_hist,
        color=colors, 
        bins=bins, 
        histtype='bar', 
        stacked=True
    )
    plt.xlim(0, max_)
    plt.legend(loc='upper right')
    plt.title(title)
    plt.yscale('log')
    plt.xlabel('patch size (px)')
    plt.ylabel('number of pixels')

    plt.savefig(filepath)   # save the figure to file
    
    return filepath
    
def create_csv(df, aoi_name, glad_dir, date_range):
    
    Y_conf = df[df['conf'] != 0]['conf'].to_numpy()
    unique, counts = np.unique(Y_conf, return_counts=True)
    conf_dict = dict(zip(unique, counts))
    #null if all the alerts have been confirmed
    Y_prob = df[df['prob'] != 0]['prob'].to_numpy()
    unique, counts = np.unique(Y_prob, return_counts=True)
    prob_dict = dict(zip(unique, counts))
        
    #add missing keys to conf
    conf_dict = utils.complete_dict(conf_dict, prob_dict) 
    prob_dict = utils.complete_dict(prob_dict, conf_dict)
    
    df2 = pd.DataFrame([conf_dict, prob_dict], index=['confirmed alerts', 'Potential alerts'])
    
    filename = glad_dir + aoi_name + '_{}_{}_distrib.csv'.format(date_range[0],date_range[1])
    df2.to_csv(filename)
    
    return filename

def display_alerts(aoi_name, year, date_range):
    """dipslay the selected alerts on the geemap
    currently re-computing the alerts on the fly because geemap is faster to use ee interface than reading a .tif file
    """
    
    #create the map
    m = utils.init_result_map()
    
    aoi = ee.FeatureCollection(aoi_name)
    alerts_date = gee_process.get_alerts_dates(aoi_name, year, date_range)
    alerts = gee_process.get_alerts(aoi_name, year, alerts_date)
    alertsMasked = alerts.updateMask(alerts.gt(0));
    
    palette = pm.getPalette()
    m.addLayer(alertsMasked, {
        'bands':['conf' + str(year%100)], 
        'min':2, 
        'max':3, 
        'palette': palette[::-1]
    }, 'alerts') 
    
    #Create an empty image into which to paint the features, cast to byte.
    empty = ee.Image().byte()
    outline = empty.paint(**{'featureCollection': aoi, 'color': 1, 'width': 3})
    m.addLayer(outline, {'palette': '283593'}, 'aoi')
                 
    m.centerObject(aoi, zoom=mapping.update_zoom(aoi_name))
    
    legend_keys = ['potential alerts', 'confirmed alerts']
    legend_colors = palette[::-1]
    
    m.add_legend(legend_keys=legend_keys, legend_colors=legend_colors, position='topleft')
    
    return m
                 
    
    
    
