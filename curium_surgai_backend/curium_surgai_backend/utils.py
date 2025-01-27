import boto3
import json
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class S3Utils:
    def __init__(self, bucket_name, access_key=None, secret_key=None, region=None):
        self.bucket_name = bucket_name
        self.aws_access_key = access_key
        self.aws_secret_access_key = secret_key
        self.aws_region = region
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.aws_region,
        )

    def upload_file(self, file_location, key):
        self.s3.upload_file(file_location, self.bucket_name, key)

    def get_s3_object(self, file_location):
        try:
            s3_response = self.s3.get_object(Bucket=self.bucket_name, Key=file_location)
            s3_object_body = s3_response.get("Body")
            content = s3_object_body.read()
            try:
                json_dict = json.loads(content)
                return json_dict
            except json.decoder.JSONDecodeError as e:
                logger.exception(e)
        except ClientError as e:
            logger.exception(e)

    def generate_presigned_url(self, object_key, expiry=604800):
        try:
            response = self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expiry,
            )
        except ClientError as e:
            logger.error(f"key not found {object_key}")
            logger.exception(e)
        return response
