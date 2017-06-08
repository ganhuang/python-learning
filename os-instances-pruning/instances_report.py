#!/usr/bin/python
#coding:utf-8

# Author: Gan Huang (ghuang@redhat.com)
# OpenStacksdk: http://developer.openstack.org/sdks/python/openstacksdk/
# pip install openstacksdk

import yaml
import smtplib
import time
import textwrap

from openstack import connection

class OpenStackAPI():

    def __init__(self, iaas_name, config):

        self.conn = connection.Connection(auth_url = config[iaas_name]['OS_AUTH_URL'],
                                     project_name = config[iaas_name]['OS_TENANT_NAME'],
                                     username = config[iaas_name]['OS_USERNAME'],
                                     password = config[iaas_name]['OS_PASSWORD'])
    def list_servers(self):
        return self.conn.compute.servers()

    def get_server_floating_ip(self, server):
        return server.addresses[OS_TENANT_NAME][1]['addr']

    def get_server_type(self, flavor_id):
        return self.conn.compute.get_flavor(flavor_id).name

# TODO: send email periodically for long-running instance with "preserve" tags
def sendMail(FROM, TO, SUBJECT, TEXT, SERVER):
    """this is some test documentation in the function"""
    message = textwrap.dedent("""\
From: %s
To: %s
Subject: %s

Please terminate following instances if no longer needed.

Please adjust the instance flavor accordingly for saving resources.
vm_type: m1.small/m1.medium/m1.large
###################################################################

%s
""" % (FROM, ", ".join(TO), SUBJECT, TEXT))
    # Send the mail
    server = smtplib.SMTP(SERVER)
    server.sendmail(FROM, TO, message)
    server.quit()

def compare_time(created_time, time_limit):
    # we should use UTC time
    timeArray = time.strptime(created_time, "%Y-%m-%dT%H:%M:%SZ")
    created_time_stamp = time.mktime(timeArray)
    current_time = time.mktime(time.gmtime())
    if current_time - created_time_stamp > time_limit:
        running_days = (current_time - created_time_stamp)/86400
        return True, running_days 
    else:
        return False, None 


if __name__ == '__main__':

  with open("../prune.yaml", 'r') as cf:
      try:
          config = yaml.load(cf)
      except yaml.YAMLError as exc:
          print(exc)

  # get global variables from prune.yaml
  instance_running_threshold = config['INSTANCE_RUNNING_THRESHOLD']
  instance_white_list_keywords_for_report = config['INSTANCE_WHITE_LIST_KEYWORDS_FOR_REPORT']
  email_to = config['EMAIL_TO']
  email_from = config['EMAIL_FROM']
  email_subject = config['EMAIL_SUBJECT']
  email_server = config['EMAIL_SERVER']
  email_text = []

  for iaas_name in config['IAAS_LIST']:

      conn_OS = OpenStackAPI(iaas_name, config)
      for server in conn_OS.list_servers():

          # get instance parameters for next steps
          created_time = server.created_at
          instance_name = server.name
          instance_preserve = False
          flavor_id = server.flavor["id"]
          instance_type = conn_OS.get_server_type(flavor_id)

          # check if the instance has the "white_list" keyword defined in prune.yaml
          for keyword in instance_white_list_keywords_for_report:
              if keyword in instance_name.lower():
                  instance_preserve = True
                  break

          if not instance_preserve:
              exceed_bool, instance_running_days =  compare_time(created_time, instance_running_threshold)
              if exceed_bool:
                  email_text.append("%50s (%s) | %5s days | %5s OpenStack\n" % (instance_name, instance_type, int(instance_running_days), iaas_name))
  if email_text:
      email_text_string = '\n'.join(email_text)
      sendMail(email_from, email_to, email_subject, email_text_string, email_server )
