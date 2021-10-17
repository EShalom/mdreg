"""
MODEL DRIVEN REGISTRATION for iBEAt study: quantitative renal MRI
@Kanishka Sharma 2021
Test script for DCE sequence using Model driven registration Library
"""
import sys
import glob
import os
import numpy as np
import itk
import SimpleITK as sitk
import pydicom
from pathlib import Path 
import time
from PIL import Image
from MDR import model_driven_registration  
import importlib


np.set_printoptions(threshold=sys.maxsize)


def main():
    # selected sequence to process
    sequence = 'DCE'
    # number of expected slices to process (example: iBEAt study number of slice = 9)
    slices = 9    

    # path definition  
    # your 'os.getcwd()' path should point to your local directory containing the  MDR-Library 
    # eg: /Users/kanishkasharma/Documents/GitHub/MDR_Library
    print(os.getcwd()) 

    DATA_PATH = os.getcwd() + r'/tests/test_data/DICOMs'
    AIFs_PATH = os.getcwd() + r'/tests/test_data/AIFs' 
    OUTPUT_REG_PATH = os.getcwd() + r'/MDR_registration_output'
    Elastix_Parameter_file_PATH = os.getcwd() + r'/Elastix_Parameters_Files/iBEAt' 
    output_dir =  OUTPUT_REG_PATH + '/DCE/'

    # Organize files per each sequence:
    os.chdir(DATA_PATH)    
    # list all patient folders available to be processed
    patients_folders = os.listdir()
    # select patient folder to be processed from the list of available patient DICOMs supplied in patients_folders
    for patient_folder in patients_folders:
        if patient_folder not in ['test_case_iBEAt_4128009']: # eg: test case selected to be processed - change to your own test case
            continue
        # read path to the sequence to be processed for selected test patient case: eg: DCE
        sequence_images_path = patient_folder + '/' + str(sequence) + '/DICOM'
        os.chdir(DATA_PATH + '/' + sequence_images_path)
        # read all dicom files for selected sequence
        dcm_files_found = glob.glob("*.dcm")
        if not dcm_files_found:
            dcm_files_found = glob.glob("*.IMA") # if sequence is IMA format instead of dcm
        # slice to be processed from selected sequence
        for slice in range(1, slices+1):
            current_slice = sequence + '_slice_' + str(slice)
            # single slice processing for DCE sequence (here selected slice number is 5)
            if current_slice not in [sequence + '_slice_5']:
                continue
            # read slice path to be processed
            slice_path = DATA_PATH + '/' + sequence_images_path + '/' + current_slice
            data = Path(slice_path)
            # list of all DICOMs to be processed for the selected slice (example: slice number = 5 here)
            lstFilesDCM = list(data.glob('**/*.IMA')) 
    
            # read all dicom files for the selected sequence and slice
            files, ArrayDicomiBEAt, filenameDCM = read_DICOM_files(lstFilesDCM)
            # get sitk image parameters for registration (origin and spacing)
            image_parameters = get_sitk_image_details_from_DICOM(slice_path)
            # sort slices correctly - based on acquisition time for model driven registration
            sorted_slice_files = sort_all_slice_files_acquisition_time(files)
            # run DCE MDR test 
            iBEAt_test_DCE(Elastix_Parameter_file_PATH, output_dir, sorted_slice_files, ArrayDicomiBEAt, image_parameters, AIFs_PATH, patient_folder)

# read input dicom files
def read_DICOM_files(lstFilesDCM):
    files = []
    RefDs = pydicom.dcmread(lstFilesDCM[0])
    SeriesPixelDims = (int(RefDs.Rows), int(RefDs.Columns), len(lstFilesDCM))           
    ArrayDicomiBEAt = np.zeros(SeriesPixelDims, dtype=RefDs.pixel_array.dtype)

    # read all dicoms and output dicom files
    for filenameDCM in lstFilesDCM: 
        files.append(pydicom.dcmread(filenameDCM))
        ds = pydicom.dcmread(filenameDCM)
        # write pixel data into numpy array
        ArrayDicomiBEAt[:, :, lstFilesDCM.index(filenameDCM)] = ds.pixel_array  


    return files, ArrayDicomiBEAt, filenameDCM

# get input image origin and spacing to set the numpy arrays for registration
def get_sitk_image_details_from_DICOM(slice_path):
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(slice_path)
    reader.SetFileNames(dicom_names)
    image = reader.Execute()
    spacing = image.GetSpacing() 
    return spacing

# sort all input slices based on acquisition time
def sort_all_slice_files_acquisition_time(files):
    slice_sorted_acq_time = []
    skipcount = 0
    for f in files: 
        if hasattr(f, 'AcquisitionTime'):
            slice_sorted_acq_time.append(f)
        else:
            skipcount = skipcount + 1
    print("skipped, no AcquisitionTime: {}".format(skipcount))

    return sorted(slice_sorted_acq_time, key=lambda s: s.AcquisitionTime)  

# test DCE using model driven registration
def iBEAt_test_DCE(Elastix_Parameter_file_PATH, output_dir, sorted_slice_files, ArrayDicomiBEAt, image_parameters, AIFs_PATH, patient_folder):
    """ Example application of MDR in renal DCE (iBEAt data)
    
    Args
    ----
    Elastix_Parameter_file_PATH (string): complete path to the Elastix parameter file to be used
    output_dir (string): directory where results are saved
    slice_sorted_files (list): selected slices to process using MDR - sorted according to acquisition time 
    ArrayDicomiBEAt (numpy.ndarray): input DICOM to numpy array (unsorted)
    image_parameters (stik tuple): distance between pixels (in mm) along each dimension.
    AIFs_PATH (string): string with full AIF path
    patient_folder (string): patient folder with AIFs text file

    Description
    -----------
    This function performs model driven registration for selected DCE sequence on a single selected slice 
    and returns as output the MDR registered images, signal model fit, deformation field x, deformation field y, 
    fitted parameters Fp, Tp, Ps, Te, and the final diagnostics.
    """
    start_computation_time = time.time()
    # define numpy array with same input shape as original DICOMs
    image_shape = np.shape(ArrayDicomiBEAt)
    original_images = np.zeros(image_shape)

    # initialise original_images with sorted acquisiton times to run MDR
    for i, s in enumerate(sorted_slice_files):
        img2d = s.pixel_array
        original_images[:, :, i] = img2d

    # read signal model parameters
    full_module_name = "models.iBEAt_DCE"
    signal_model_parameters = read_signal_model_parameters(full_module_name,AIFs_PATH, patient_folder)
    # read signal model parameters
    elastix_model_parameters = read_elastix_model_parameters(Elastix_Parameter_file_PATH)
    
    #Perform MDR
    MDR_output = model_driven_registration(original_images, image_parameters, signal_model_parameters, elastix_model_parameters, precision = 1)

    #Export results
    export_images(MDR_output[0], output_dir +'/coregistered/MDR-registered_DCE_')
    export_images(MDR_output[1], output_dir +'/fit/fit_image_')
    export_images(MDR_output[2][:,:,0,:], output_dir +'/deformation_field/final_deformation_x_')
    export_images(MDR_output[2][:,:,1,:], output_dir +'/deformation_field/final_deformation_y_')
    export_maps(MDR_output[3][::4], output_dir + '/fitted_parameters/Fp', np.shape(original_images))
    export_maps(MDR_output[3][1::4], output_dir + '/fitted_parameters/Tp', np.shape(original_images))
    export_maps(MDR_output[3][2::4], output_dir + '/fitted_parameters/Ps', np.shape(original_images))
    export_maps(MDR_output[3][3::4], output_dir + '/fitted_parameters/Te', np.shape(original_images))
    MDR_output[4].to_csv(output_dir + 'DCE_largest_deformations.csv')

    # Report computation times
    end_computation_time = time.time()
    print("total computation time for MDR (minutes taken:)...")
    print(0.0166667*(end_computation_time - start_computation_time)) # in minutes
    print("completed MDR registration!")
    print("Finished processing Model Driven Registration case for iBEAt study DCE sequence!")



## read sequence acquisition parameter for signal modelling
def read_signal_model_parameters(full_module_name,AIFs_PATH, patient_folder):
   
   # generate a module named as a string
    MODEL = importlib.import_module(full_module_name)
    aif, times = MODEL.load_txt(AIFs_PATH + '/' + str(patient_folder) + '/' + 'AIF__2C Filtration__Curve.txt')
    aif.append(aif[-1])
    times.append(times[-1])
    # select signal model paramters
    signal_model_parameters = [MODEL, [aif, times]]
    return signal_model_parameters


## read elastix parameters
def read_elastix_model_parameters(Elastix_Parameter_file_PATH):
    elastix_model_parameters = itk.ParameterObject.New()
    elastix_model_parameters.AddParameterFile(Elastix_Parameter_file_PATH + "/BSplines_DCE.txt")
    elastix_model_parameters.SetParameter('MaximumNumberOfIterations', '256')
    return elastix_model_parameters


## Save MDR results to folder
def export_images(MDR_output, folder):
    shape = np.shape(MDR_output)
    for i in range(shape[2]):
        im = Image.fromarray(MDR_output[:,:,i])
        im.save(folder + str(i) + ".tiff")


## Fitted Parameters to output folder
def export_maps(MDR_output, folder, shape):
    array = np.reshape(MDR_output, [shape[0],shape[1]]) 
    Img = Image.fromarray(array)
    Img.save(folder + ".tiff")
    