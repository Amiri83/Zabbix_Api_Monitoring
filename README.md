# Zabbix_Api_Monitoring
Monitor Specific API Call Success/Failure Rates and TPS from Nginx Logs Using Python, Zabbix, and Grafana


## Sample Dashboard

![Dashboard_sample](docs/dashboard_sample.png)


## Background & Problem
Our system made high-frequency API calls to a third-party service via an Nginx reverse proxy. We were sending thousands of requests per second, but when the third-party service had issues, our calls would fail without warning.

Because we had no access to the third-party system, we relied on our Nginx access logs to monitor API call health. The challenge was to detect issues quickly and understand the impact.

here is sample of our revres proxy nginx config file 

<pre>log_format apilogs
    '$remote_addr $remote_user [$time_local] '
    '$request_method '
    '$request_uri '
    '$status $body_bytes_sent '
    '$request_time ($upstream_response_time) '
    'apicalls '
    '"$http_user_agent" "$http_x_forwarded_for" "$http_referer"';
server {
    listen PORT;
    keepalive_timeout 60;
    send_timeout 60;
    location / {
        proxy_pass  http://YOUR3rdPartyIP:Your3rdPartyPORT$request_uri;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        access_log  /var/log/nginx/apipostdata.log apilogs;
    }
}
  </pre>
## Why Can't We Use Zabbix log.count?

The problem with using Zabbix’s log.count function to calculate success/failure rates and TPS (Transactions Per Second) is related to timestamp accuracy.
Zabbix pollers operate on their own schedule to sample log files, independent of the actual timestamps in the logs. This can lead to inaccurate TPS values and misaligned success/failure counts.
For accurate monitoring, all metrics — success, failure, and TPS — must be measured based on the same timestamp window derived from the log entries themselves, not the poller's sampling interval.

## Soultion 
We use a Python script to process log data, extract key metrics (success/failure counts and TPS), and send them directly to Zabbix via trapper items. This ensures accurate, timestamp-aligned monitoring, independent of Zabbix’s polling schedule.

<p align="center">
  <img src="docs/log_flow.png" alt="Log Flow Diagram" style="margin-top: 20px; margin-bottom: 20px; border-radius: 8px;"/>
</p>

Since some API calls occur during off-peak times when no requests may be made, this could negatively impact success rate calculations. To address this, the script reports a 100% success rate during off-peak periods to maintain consistent KPI monitoring, even when no API calls are made.

Configuration
The user defines:

ServiceName: The name of the API being monitored.
Zabbix Hostname: The target host in Zabbix to receive the metrics.
Success/Total Conditions: Regular expressions used to identify successful and total API calls in the logs.
The script calculates the log analysis window by subtracting one minute from the current system time (date -1 min) and applies the configured regex patterns to extract metrics from the logs.

Total: Specifies the regex pattern used to count the total number of API calls.
Success: Specifies the regex pattern used to count successful API calls.
Off-peak period: Defines the time range during which the success rate is forcibly reported as 100%, even if the number of API calls is zero. If this value is set to null, the condition is ignored.



## Implemenation 
1.Copy and configure the parser.py file on your server.

When you run it, you should see output similar to the example below, depending on your defined patterns and the number of APIs being monitored.


<pre>
api-host recovery.success.rate 100.00
api-host recovery.success.request 338
api-host recovery.total.request 338
api-host recovery.failed.request 0
api-host recovery.failed.rate 0.00
api-host recovery.tps.rate 23
api-host lending.success.rate 100.00
api-host lending.success.request 348
api-host lending.total.request 348
api-host lending.failed.request 0
api-host lending.failed.rate 0.00
api-host lending.tps.rate 12
api-host auto.success.rate 100.00
api-host auto.success.request 424
api-host auto.total.request 424
api-host auto.failed.request 0
api-host auto.failed.rate 0.00
api-host auto.tps.rate 14
</pre>

### Note: The API host should already be added to your Zabbix server

2.Install Zabbix Sender (Trapper Support)
Make sure zabbix_sender is installed on your system. This tool is required to send data to Zabbix trapper items
for debian base
<pre>
sudo apt install zabbix-sender 
</pre>
or 
<pre>
sudo dnf install zabbix-sender 
</pre>
for Redhatbase

3. add crontab for parse like below (I added for each 2 min you can define your own) 
<pre>
*/2 * * * * root python3 /path/to/parser.py  > /tmp/zbx.txt && zabbix_sender -c /etc/zabbix/zabbix_agent2.conf -i /tmp/zbx.txt
</pre>

4.The parser provides 6 KPIs per API. You can add the desired items to your Zabbix configuration as needed.
Here is a sample:
first go to your api-host on zabbix and add item as below

![zabbix_item_config](docs/zabbix_item_config.png)

Set the item type to Zabbix Trapper and use the exact key as shown in the parser.py output.
The data type should be set to float.

Repeat this process for all the items you need. Once configured, the data will be available in Zabbix.
If you have an integration between Zabbix and Grafana, you can now visualize the metrics in Grafana dashboards.


