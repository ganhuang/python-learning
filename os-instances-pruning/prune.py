#!/usr/bin/python
#coding:utf-8

# Author: Gan Huang (ghuang@redhat.com)
# OpenStacksdk: http://developer.openstack.org/sdks/python/openstacksdk/
# pip install openstacksdk

import yaml
import smtplib
import logging
import time
import openstack
import colorer

class OpenStackAPI():

    def __init__(self, iaas_name, config):

        self.conn = openstack.connection.Connection(auth_url = config[iaas_name]['OS_AUTH_URL'],
                                     project_name = config[iaas_name]['OS_TENANT_NAME'],
                                     username = config[iaas_name]['OS_USERNAME'],
                                     password = config[iaas_name]['OS_PASSWORD'])

    def list_servers(self):
        return self.conn.compute.servers()

    def get_server_floating_ip(self, server):
        return server.addresses[OS_TENANT_NAME][1]['addr']

    def stop_server(self, instance_name, instance_uuid):
        try: 
            if not dry_run:
                self.conn.compute.stop_server(instance_uuid)
            logging.warning('Instance %s stopped', instance_name)
        except Exception as exc:
            logging.error('Instance %s can not be stopped', instance_name)
            logging.error('%s', exc)

    def delete_server(self, instance_name, instance_uuid):
        try: 
            if not dry_run:
                self.conn.compute.delete_server(instance_uuid)
            logging.warning('Instance %s terminated', instance_name)
        except Exception as exc:
            logging.error('Instance %s can not be terminated', instance_name)
            logging.error('%s', exc)

def compare_time(created_time, time_limit):
    # we should use UTC time
    timeArray = time.strptime(created_time, "%Y-%m-%dT%H:%M:%SZ")
    created_time_stamp = time.mktime(timeArray)
    current_time = time.mktime(time.gmtime())
    if current_time - created_time_stamp > time_limit:
        running_hours = (current_time - created_time_stamp)/3600
        return True, running_hours
    else:
        return False, None

def stop_old_instance(created_time, instance_name, instance_uuid):
    exceed_bool, instance_running_hours = compare_time(created_time, stop_time_limit)
    if exceed_bool:
        logging.info('Instance %s running for %.2f hours', instance_name, instance_running_hours)
        conn_OS.stop_server(instance_name, instance_uuid)
        # sleep here in case the OpenStack server is under high pressure
        time.sleep(1)

def terminate_old_instance(created_time, instance_name, instance_uuid):
    exceed_bool, instance_running_hours = compare_time(created_time, delete_stopped_time_limit)
    if exceed_bool:
        logging.info('Instance %s stopped for %.2f hours', instance_name, instance_running_hours)
        conn_OS.delete_server(instance_name, instance_uuid)
        # sleep here in case the OpenStack server is under high requests
        time.sleep(1)


if __name__ == '__main__':

  with open("../prune.yaml", 'r') as cf:
      try:
          config = yaml.load(cf)
      except yaml.YAMLError as exc:
          print(exc)

  # get global variables from prune.yaml
  qe_stop_time_limit = config['QE_STOP_TIME_LIMIT']
  qe_delete_stopped_time_limit = config['QE_DELETE_STOPPED_TIME_LIMIT']
  noqe_stop_time_limit = config['NOQE_STOP_TIME_LIMIT']
  noqe_delete_stopped_time_limit = config['NOQE_DELETE_STOPPED_TIME_LIMIT']
  instances_white_list_keywords = config['INSTANCE_WHITE_LIST_KEYWORDS']
  dry_run = config['DRY_RUN']

  # customed the logging output with timestamp
  logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
  # UTC
  logging.Formatter.converter = time.gmtime

  for iaas_name in config['IAAS_LIST']:

      conn_OS = OpenStackAPI(iaas_name, config)
      for server in conn_OS.list_servers():

          # get instance parameters for next steps
          created_time = server.created_at
          is_active = (lambda x : x == "ACTIVE")(server.status)
          instance_name = server.name
          instance_uuid = server.id
          instance_preserve = False

          # check if the instance has the "white_list" keyword defined in prune.yaml
          for keyword in instances_white_list_keywords:
              if keyword in instance_name.lower():
                  instance_preserve = True
                  break

          if not instance_preserve:
              # set time_limit properly accroding to keyword "qe" in instance name
              if "qe" in instance_name.lower():
                  stop_time_limit = qe_stop_time_limit
                  delete_stopped_time_limit = qe_delete_stopped_time_limit
              else:
                  stop_time_limit = noqe_stop_time_limit
                  delete_stopped_time_limit = noqe_delete_stopped_time_limit

              if is_active:
                  stop_old_instance(created_time, instance_name, instance_uuid)
              else:
                  stopped_time = server.updated_at
                  terminate_old_instance(stopped_time, instance_name, instance_uuid)
