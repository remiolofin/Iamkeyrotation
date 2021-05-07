import boto3
iam = boto3.client('iam')
from datetime import datetime,timezone
today = datetime.now(timezone.utc)
from botocore.exceptions import ClientError
import json


secretmanager = boto3.client('secretsmanager')

def create_key(uname):
    try:
        IAM_UserName=uname
        response = iam.create_access_key(UserName=IAM_UserName)
        AccessKey = response['AccessKey']['AccessKeyId']
        SecretKey = response['AccessKey']['SecretAccessKey']
        # print("My name is " + AccessKey + " and i am the Accesskey")
        # print("My name is " + SecretKey + " and i am the SecretKey")
        json_data=json.dumps({'AccessKey' :AccessKey, 'SecretKey' :SecretKey})
        response = secretmanager.create_secret(Name=IAM_UserName)
        secmanagerv=secretmanager.put_secret_value(SecretId=IAM_UserName,SecretString=json_data)
        print(" A Secret was created for " + IAM_UserName + ' and the access and secret has been dumped there')
        emailmsg= "New "+AccessKey+" has been created. Please get the secret value from secret manager"
        ops_sns_topic = "arn:aws:sns:us-east"
        sns_send_report = boto3.client('sns',region_name='us-east-1')
        sns_send_report.publish(TopicArn=ops_sns_topic, Message=emailmsg, Subject ="New Key created for user"+  IAM_UserName)
    except ClientError as e:
        print("I Couldnt create any access key right now. See Error below")
        print (e)
accesskey_list=[]
past_90_keys_list=[]


def check_for_expired_keys():
    iam_users=iam.list_users().get('Users')
    for u in iam_users:
        uname=u.get('UserName')
        user_key_details=iam.list_access_keys(UserName=uname).get('AccessKeyMetadata')
        # print(uname + ' has ' + str(len(user_key_details)) +' Accesskeys')
        if len(user_key_details)== 1: #if this user has more than one access key?
            
            user_key_details=user_key_details[0]
            user_key_created_date=user_key_details.get('CreateDate')
            user_access_key=user_key_details.get('AccessKeyId')
            length_keys= str(today - user_key_created_date)
            
            if 'day' in length_keys:
                len_keys_days=length_keys.split('day')[0]
                if int(len_keys_days)>= 40:
                    # print(uname + ' has been created for ' + length_keys)
                    past_90_keys_dict={'uname':uname, 'access':user_access_key}
                    past_90_keys_list.append(past_90_keys_dict)
            #print('Hey I am ' + uname + ', my accesskey is ' + user_access_key + ' and I was created on ' + str(user_key_created_date))
                    # print('My name is ' + uname + ' and I have only one accesskey')
            
        elif len(user_key_details)== 2:
            #print("I found 2 Access Keys for " + uname)
            # print('My name is ' + uname + ' and I have only one accesskey')
            user_key_details1=user_key_details[0]
            user_key_details2=user_key_details[1]
            user_key_created_date1=user_key_details1.get('CreateDate')
            user_key_created_date2=user_key_details2.get('CreateDate')
            len_days_diff = user_key_created_date2 - user_key_created_date1
            user_access_key1=user_key_details1.get('AccessKeyId')
            user_access_key2=user_key_details2.get('AccessKeyId')
            access_key1_status=user_key_details1.get('Status')
            access_key2_status=user_key_details2.get('Status')
            if 'days' in str(len_days_diff):
                print("Wow! " + uname + ' has 2 access keys created on different days and their difference is ' + str(len_days_diff))
                len_days_diff=str(len_days_diff).split('days')[0]
                if 0 < abs(int(len_days_diff)) < 40: 
                    # print(uname + ' is so lucky. None of its access keys has a difference in creation date more than 5 days')
                    pass
                elif 40 <= abs(int(len_days_diff)) < 90: 
                    # print ('oops! one of ' + uname + ' key will be deactivated')
                    if user_key_created_date2 > user_key_created_date1:
                        iam.update_access_key(AccessKeyId=user_access_key1, Status='Inactive', UserName=uname)
                    else:
                        iam.update_access_key(AccessKeyId=user_access_key2, Status='Inactive', UserName=uname)
                elif abs(int(len_days_diff)) >= 90:
                    print ('Dang! one of ' + uname + ' key stand a chance of deletion')
                    if user_key_created_date2 > user_key_created_date1 and access_key2_status == 'Active' and access_key1_status == 'Inactive' :
                        iam.delete_access_key(AccessKeyId=user_access_key1, UserName=uname)
                    elif user_key_created_date1 > user_key_created_date2 and access_key1_status == 'Active' and access_key2_status == 'Inactive' :
                        iam.delete_access_key(AccessKeyId=user_access_key2, UserName=uname)
                    else:
                        print( " I am sorry, i canot Delete Any keys now because one of the latest keys might be inactive and that will cause a lot of damage")
            #this means the user must have 2 keys. So we have to compare both keys
        else:
            pass
    return past_90_keys_list


past_90_days_keys=check_for_expired_keys()

def createkeyForPast90(acccess_keys_list):
    for ak in acccess_keys_list:
        fuser_name=ak.get('uname')
        print("I will be creating secret and access keys for " + fuser_name + " and I will be storing them in Secret manager" )
        status = create_key(fuser_name)
        print (status)


def lambda_handler(event, context):
    past_90_days_keys=check_for_expired_keys()
    createkeyForPast90(past_90_days_keys)
