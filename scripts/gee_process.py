import os
import ee
import time
import sys
from datetime import datetime
sys.path.append("..") # Adds higher directory to python modules path
from utils import utils
from scripts import gdrive
from utils import parameters as pm

#initialize earth engine
ee.Initialize()

#Message
TASK_COMPLETED = "The task {0} launched on your GEE account is now completed"
ALREADY_COMPLETED = "The task {0} has already been completed on your GEE account"
TASK_RUNNING = "The task {} is runnning on your GEE account"

def download_to_disk(filename, image, aoi_name, output):
    """download the tile to the GEE disk
    
    Args:
        filename (str): descripsion of the file
        image (ee.FeatureCollection): image to export
        aoi_name (str): Id of the aoi used to clip the image
        
    Returns:
        download (bool) : True il a task is running, false if not
    """
    
    def launch_task(filename, image, aoi_name, output):
        """check if file exist and launch the process if not"""
        
        download = False
        
        drive_handler = gdrive.gdrive()
        files = drive_handler.get_files(filename) 
        
        if files == []:
            task_config = {
                'image':image,
                'description':filename,
                'scale': 30,
                'region':ee.FeatureCollection(aoi_name).geometry(),
                'maxPixels': 1e13
            }
            
            task = ee.batch.Export.image.toDrive(**task_config)
            task.start()
            download = True
        else:
            utils.displayIO(output, 'success', ALREADY_COMPLETED.format(filename))
        
        return download
    
    task = utils.search_task(filename)
    if not task:
        download = launch_task(filename, image, aoi_name, output)
    else:
        if task.state == 'RUNNING':
            utils.displayIO(output, 'info', TASK_RUNNING.format(filename))
            download = True
        else: 
            download = launch_task(filename, image, aoi_name, output)
            
    return download

def get_alerts_dates(aoi_name, year, date_range):
    """return the julian day map of the glad alerts included between the two dates of date_range"""
    
    aoi = ee.FeatureCollection(aoi_name)
    if year < pm.getLastUpdatedYear():
        all_alerts = ee.ImageCollection('projects/glad/alert/{}final'.format(year))
    else:
        all_alerts = ee.ImageCollection('projects/glad/alert/UpdResult')
        
    #create the composit band alert_date. cannot use the alertDateXX band directly because they are not all caster to the same type
    dates = all_alerts.select('alertDate{}'.format(year%100)).map(
        lambda image: image.uint16()
    ).mosaic().clip(aoi)

    #masked all the images that are not between the limits dates
    
    #extract julian dates
    start = datetime.strptime(date_range[0], '%Y-%m-%d').timetuple().tm_yday
    end = datetime.strptime(date_range[1], '%Y-%m-%d').timetuple().tm_yday
    
    date_masked = dates.updateMask(dates.gt(start).And(dates.lt(end)))
    
    return date_masked    

def get_alerts(aoi_name, year, date_masked):
    """ get the alerts from the GLAD project
    
    Args:
        aoi_name (str): Id of the Aoi to retreive the alerts
        year, (str): year of alerts in format YYYY
        date_masked (ee.Image): the image of the date filter with the given date range
        
    Returns:
        alerts (ee.FeatureCollection): the Glad alert clipped on the AOI
    """
    
    aoi = ee.FeatureCollection(aoi_name)
    if year < pm.getLastUpdatedYear():
        all_alerts = ee.ImageCollection('projects/glad/alert/{}final'.format(year))
    else:
        all_alerts = ee.ImageCollection('projects/glad/alert/UpdResult')
    
        
    alerts = all_alerts.select('conf' + str(year%100)).mosaic().clip(aoi);
    
    #use the mask of the julian alerts 
    alerts = alerts.updateMask(date_masked.mask())
    
    return alerts
    
def gee_process(asset_name, date_range, year, widget_alert):
    
    global widget_gee_process_alert
    
    #check for the julian day task 
    filename_date = utils.construct_filename(asset_name, date_range) + '_dates'
    alerts_date = get_alerts_dates(asset_name, year, date_range)
    download = download_to_disk(filename_date, alerts_date, asset_name, widget_alert)
    
    #reteive alert date masked with date range 
    filename = utils.construct_filename(asset_name, date_range) + '_map'
    alerts = get_alerts(asset_name, year, alerts_date)
    download = download_to_disk(filename, alerts, asset_name, widget_alert)
    
    #wait for completion 
    # I assume that there is 2 or 0 file to launch 
    # if one of the 2 process have been launch individually it will crash
    if download:
        utils.wait_for_completion([filename, filename_date], widget_alert)
        utils.displayIO(widget_alert, 'success', TASK_COMPLETED.format(filename)) 
        
    