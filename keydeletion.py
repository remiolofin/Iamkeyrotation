from collections import defaultdict
from datetime import datetime, timezone
import logging

import boto3
from botocore.exceptions import ClientError


# How many days before sending alerts about the key age?
ALERT_AFTER_N_DAYS = 90
# How ofter we have set the cron to run the Lambda?
SEND_EVERY_N_DAYS = 3
# Who send the email?
SES_SENDER_EMAIL_ADDRESS = 'example@example.com'
# Where did we setup SES?
SES_REGION_NAME = 'eu-east-1'

iam_client = boto3.client('iam')
ses_client = boto3.client('ses', region_name=SES_REGION_NAME)

# Helper function to choose if a key owner should be notified today
def is_key_interesting(key):
    # If the key is inactive, it is not interesting
    if key['Status'] != 'Active':
        return False
    
    elapsed_days = (datetime.now(timezone.utc) - key['CreateDate']).days
    
    # If the key is newer than ALERT_AFTER_N_DAYS, we don't need to notify the
    # owner
    if elapsed_days < ALERT_AFTER_N_DAYS:
        return False
    
    return True
    
# Helper to send the notification to the user. We need the receiver email, 
# the keys we want to notify the user about, and on which account we are
def send_notification(email, keys, account_id):
    email_text = f'''Dear {keys[0]['UserName']},
this is an automatic reminder to rotate your AWS Access Keys at least every {ALERT_AFTER_N_DAYS} days.

At the moment, you have {len(keys)} key(s) on the account {account_id} that have been created more than {ALERT_AFTER_N_DAYS} days ago:
'''
    for key in keys:
        email_text += f"- {key['AccessKeyId']} was created on {key['CreateDate']} ({(datetime.now(timezone.utc) - key['CreateDate']).days} days ago)\n"
    
    email_text += f"""
To learn how to rotate your AWS Access Key, please read the official guide at https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html#Using_RotateAccessKey
If you have any question, please don't hesitate to contact the Support Team at support@example.com.

This automatic reminder will be sent again in {SEND_EVERY_N_DAYS} days, if the key(s) will not be rotated.

Regards,
Your lovely Support Team
"""
    
    try:
        ses_response = ses_client.send_email(
            Destination={'ToAddresses': [email]},
            Message={
                'Body': {'Html': {'Charset': 'UTF-8', 'Data': email_text}},
                'Subject': {'Charset': 'UTF-8',
                            'Data': f'Remember to rotate your AWS Keys on account {account_id}!'}
            },
            Source=SES_SENDER_EMAIL_ADDRESS
        )
    except ClientError as e:
        logging.error(e.response['Error']['Message'])
    else:
        logging.info(f'Notification email sent successfully to {email}! Message ID: {ses_response["MessageId"]}')

def lambda_handler(event, context):
    users = []
    is_truncated = True
    marker = None
    
    # We retrieve all users associated to the AWS Account.  
    # Results are paginated, so we go on until we have them all
    while is_truncated:
        # This strange syntax is here because `list_users` doesn't accept an 
        # invalid Marker argument, so we specify it only if it is not None
        response = iam_client.list_users(**{k: v for k, v in (dict(Marker=marker)).items() if v is not None})
        users.extend(response['Users'])
        is_truncated = response['IsTruncated']
        marker = response.get('Marker', None)
    
    # Probably in this list you have bots, or users you want to filter out
    # You can filter them by associated tags, or as I do here, just filter out 
    # all the accounts that haven't logged in the web console at least once
    # (probably they aren't users)
    filtered_users = list(filter(lambda u: u.get('PasswordLastUsed'), users))
    
    interesting_keys = []
    
    # For every user, we want to retrieve the related access keys
    for user in filtered_users:
        response = iam_client.list_access_keys(UserName=user['UserName'])
        access_keys = response['AccessKeyMetadata']
        
        # We are interested only in Active keys, older than
        # ALERT_AFTER_N_DAYS days
        interesting_keys.extend(list(filter(lambda k: is_key_interesting(k), access_keys)))
    
    # We group the keys by owner, so we send no more than one notification for every user
    interesting_keys_grouped_by_user = defaultdict(list)
    for key in interesting_keys:
        interesting_keys_grouped_by_user[key['UserName']].append(key)

    for user in interesting_keys_grouped_by_user.values():
        # In our AWS account the username is always a valid email. 
        # However, you can recover the email from IAM tags, if you have them
        # or from other lookups
        # We also get the account id from the Lambda context, but you can 
        # also specify any id you want here, it's only used in the email 
        # sent to the users to let them know on which account they should
        # check
        send_notification(user[0]['UserName'], user, context.invoked_function_arn.split(":")[4])
