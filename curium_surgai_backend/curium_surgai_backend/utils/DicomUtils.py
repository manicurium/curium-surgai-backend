import pydicom as pyd
import os
from pydicom.uid import generate_uid
import logging


logger = logging.getLogger(__name__)


class DicomUtil:
    def __init__(self, dicom_file_path):
        self.dicom_file_path = dicom_file_path
        self.ds = pyd.dcmread(dicom_file_path)

    def _get_attribute(self, attribute_name):
        # Helper function to fetch an attribute value and handle missing values
        return getattr(self.ds, attribute_name, None)

    def fetch_patient_details(self):
        # Fetch patient details
        patient_name = self._get_attribute("PatientName")
        patient_age = self._get_attribute("PatientAge")
        patient_sex = self._get_attribute("PatientSex")
        patient_id = self._get_attribute("PatientID")
        slice_number = self._get_attribute("InstanceNumber")
        total_slices = self._get_attribute("NumberOfFrames")
        dicom_study_id = self._get_attribute("StudyID")
        institutionname = self._get_attribute("InstitutionName")
        studyinstanceuid = self._get_attribute("StudyInstanceUID")
        seriesinstanceuid = self._get_attribute("SeriesInstanceUID")
        sopinstanceuid = self._get_attribute("SOPInstanceUID")

        patient_data = {
            "PatientName": str(patient_name),
            "PatientAge": patient_age,
            "PatientSex": patient_sex,
            "PatientId": str(patient_id),
            "SliceNumber": slice_number,
            "TotalSlices": total_slices,
            "StudyId": str(dicom_study_id),
            "InstitutionName": institutionname,
            "StudyInstanceUID": str(studyinstanceuid),
            "SeriesInstanceUID": str(seriesinstanceuid),
            "SOPInstanceUID": str(sopinstanceuid),
        }

        return patient_data


def update_dicom_metadata(
    directory_path,
    anonimized_patient_id,
    annonimized_study_id,
    anonimized_institution_name,
    anonimized_patient_name,
):
    anonimized_study_instance_uid = generate_uid()
    anonimized_series_instance_uid = generate_uid()
    # Iterate through all files in the directory
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)

        # Check if the file is a DICOM file
        if not os.path.isfile(file_path):
            continue

        try:
            # Load the DICOM file
            dicom_file = pyd.dcmread(file_path)

            # Update the metadata fields
            # dicom_file.InstitutionName = anonimized_institution_name
            dicom_file.PatientName = anonimized_patient_name
            dicom_file.PatientID = anonimized_patient_id
            dicom_file.StudyID = annonimized_study_id
            # dicom_file.StudyInstanceUID = anonimized_study_instance_uid
            # dicom_file.SeriesInstanceUID = anonimized_series_instance_uid
            # Save the updated DICOM file
            dicom_file.save_as(file_path)

        except Exception as e:
            logger.exception(e)
