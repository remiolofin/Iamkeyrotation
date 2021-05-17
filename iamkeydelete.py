import json
import boto3
iam_client=boto3.client('iam')
sns_send_report = boto3.client('sns')
from datetime import datetime
from datetime import timedelta



def lambda_handler(event, context):
     expired_list=scan_acces()

     TopicArn='arn:aws:sns:us-east-1:421956431754:Iamkeyrotation'
     Msg= 'Good Day ,your acesss key is about to expire, to rotate your key visit https://docs.google.com/document/d/1nYn3KxP8G2Uba69iCnMmaqYMKx56CGekyUfA0vys4e8/edit  /n' + str(scan_acces())
     access_sns(TopicArn, Msg)



expiration_list=[]
def scan_acces():
     response = iam_client.get_group(GroupName='Architecture')
     users=response['Users']
     for userinfo in users:
         username= userinfo['UserName']
         userid= userinfo['UserId']
         access_response = iam_client.list_access_keys(UserName=username)
         access_response=access_response['AccessKeyMetadata']
         for access_keys in access_response:
             ak=access_keys['AccessKeyId']
             cd=access_keys['CreateDate']
             c_date = cd.replace(tzinfo=None)
             diff= (datetime.now() - c_date).days
             days = 0
             if diff > days:
                 delete_after = 7
                 exp_dict={'uname':username,'Access_Key':ak, 'Creation_Date':c_date}
                 del_access = iam_client.delete_access_key(UserName=username, AccessKeyId=ak)
                 expiration_list.append(exp_dict)
     return expiration_list


def access_sns(topic_arn, body_msg):
     response = sns_send_report.publish(TopicArn=topic_arn, Message=body_msg)
     return response
