import csv
import ee
import os
from datetime import datetime
import time
import ipyvuetify as v
import glob
from pathlib import Path
import geemap

#initialize earth engine
ee.Initialize()

#messages 
STATUS = "Status : {0}"

def get_aoi_name(asset_name):
    """Return the corresponding aoi_name from an assetId"""
    return os.path.split(asset_name)[1].replace('aoi_','')

def construct_filename(asset_name, date_range):
    """return the filename associated with the current task
    
    Args:
        asset_name (str): the ID of the asset
        date_range ([str, str]): the range of date to retreive the GLAD alerts (Y-m-d)
    
    Returns:
        filename (str): the filename to save the Tif files
    """
    aoi_name = get_aoi_name(asset_name)
    filename = aoi_name + '_{0}_{1}_alerts'.format(date_range[0], date_range[1]) 
    
    return filename

def complete_dict(first_dict, second_dict):
    """complete the first dict with the missing keys from the second dict. thos keys values are set to 0. return a sorted dict
    """
    for key in second_dict:
            if not key in first_dict.keys():
                first_dict[key] = 0 
            
    sorted_dict = {}
    for key in sorted(first_dict):
        sorted_dict[key] = first_dict[key]
                        
    return sorted_dict
    
def wait_for_completion(task_descripsion, widget_alert):
    """Wait until the selected process are finished. Display some output information

    Args:
        task_descripsion ([str]) : name of the running tasks
        widget_alert (v.Alert) : alert to display the output messages
    
    Returns: state (str) : final state
    """
    state = 'UNSUBMITTED'
    while not (state == 'COMPLETED' or state =='FAILED'):
        widget_alert.add_live_msg(STATUS.format(state), 'info')
        time.sleep(5)
                    
        #search for the task in task_list
        for task in task_descripsion:
            current_task = search_task(task)
            state = current_task.state
            if state == 'RUNNING': break
    
    return state

def search_task(task_descripsion):
    """Search for the described task in the user Task list return None if nothing is find
    
    Args: 
        task_descripsion (str): the task descripsion
    
    Returns
        task (ee.Task) : return the found task else None
    """
    
    tasks_list = ee.batch.Task.list()
    current_task = None
    for task in tasks_list:
        if task.config['description'] == task_descripsion:
            current_task = task
            break
            
    return current_task

def create_result_folder(aoiId):
    """Create a folder to download the glad images
   
    Args:
        aoiId(str) : the Id to the asset
    
    Returns:
        glad_dir (str): pathname to the glad_result folder
    """
    aoi = get_aoi_name(aoiId)
    glad_dir = os.path.join(os.path.expanduser('~'), 'glad_results') + '/'
        
    pathname = glad_dir + aoi + '/'
    if not os.path.exists(pathname):
        os.makedirs(pathname)
    
    return pathname

def check_for_file(filename):
    """return the file corresponding to the pathname else False
    
    Args:
        filename (str): expected pathname of the file
      
    Returns:
        (str) : the pathname if found else False
    """
    return glob.glob(filename)
           

    
      