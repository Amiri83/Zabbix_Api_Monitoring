import os
import re
import subprocess
from datetime import datetime, timedelta

# Set up the formatted date
date_l = (datetime.now() - timedelta(minutes=1)).strftime('%d/%b/%Y:%H:%M')
date_f = datetime.now().strftime('%Y%m%d')
zabbix_hostname = "api-host"


def process_logs(service_name, log_file, success_pattern, total_pattern=None, offpeak_time='none'):
    # Automatically determine the gzipped log file based on the regular log file name
    gz_log_file = f"{log_file}-{date_f}.gz"

    # Initialize the total counts
    success_total, failure_total, total_total = 0, 0, 0
    timestamps_combined = []

    # Function to calculate success, failure, and total counts from a log file using `grep`
    def check_log_file(log_file, success_pattern, total_pattern):
        total_count = 0
        success_count = 0
        timestamps = []

        try:
            # Use `grep` to filter the log file by the date and total pattern (if provided)
            if total_pattern:
                cmd = f"grep '{date_l}' {log_file} | grep '{total_pattern}'"
            else:
                cmd = f"grep '{date_l}' {log_file}"

            result = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
            lines = result.stdout.splitlines()

            for line in lines:
                total_count += 1
                if re.search(success_pattern, line):
                    success_count += 1

                # Extract the timestamp
                match = re.search(
                    r'\[([0-9]{2}/[A-Za-z]{3}/[0-9]{4}:[0-9]{2}:[0-9]{2}:[0-9]{2})', line)
                if match:
                    timestamps.append(match.group(1))

        except Exception as e:
            print(f"Error processing {log_file}: {e}")

        # Calculate failure as total - success
        failure_count = total_count - success_count

        return success_count, failure_count, total_count, timestamps

    # Function to process gzipped log file using `zcat` and `grep`
    def check_gz_file(gz_file, success_pattern, total_pattern):
        total_count = 0
        success_count = 0
        timestamps = []

        try:
            if total_pattern:
                cmd = f"zcat {gz_file} | grep '{date_l}' | grep '{total_pattern}'"
            else:
                cmd = f"zcat {gz_file} | grep '{date_l}'"

            result = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True)
            lines = result.stdout.splitlines()

            for line in lines:
                total_count += 1
                if re.search(success_pattern, line):
                    success_count += 1

                # Extract the timestamp
                match = re.search(
                    r'\[([0-9]{2}/[A-Za-z]{3}/[0-9]{4}:[0-9]{2}:[0-9]{2}:[0-9]{2})', line)
                if match:
                    timestamps.append(match.group(1))

        except Exception as e:
            print(f"Error processing {gz_file}: {e}")

        # Calculate failure as total - success
        failure_count = total_count - success_count

        return success_count, failure_count, total_count, timestamps

    # Check if gzipped log file exists
    gz_file_exists = os.path.exists(gz_log_file)

    # If gzipped file exists, process it using `zcat`
    if gz_file_exists:
        success_gz, failure_gz, total_gz, timestamps_gz = check_gz_file(
            gz_log_file, success_pattern, total_pattern)
        success_total += success_gz
        failure_total += failure_gz
        total_total += total_gz
        timestamps_combined.extend(timestamps_gz)

    # Process the regular log file using `grep`
    success_log, failure_log, total_log, timestamps_log = check_log_file(
        log_file, success_pattern, total_pattern)
    success_total += success_log
    failure_total += failure_log
    total_total += total_log
    timestamps_combined.extend(timestamps_log)

    # Check for off-peak time adjustments
    if offpeak_time != 'none':
        offpeak_start, offpeak_end = offpeak_time.split('-')
        offpeak_start = datetime.strptime(offpeak_start, '%H:%M').time()
        offpeak_end = datetime.strptime(offpeak_end, '%H:%M').time()

        in_offpeak = is_within_offpeak(offpeak_start, offpeak_end)

        # If within offpeak time and no requests were made, set success_rate to 100%
        if in_offpeak and total_total == 0:
            success_rate = 100
            failure_rate = 0
        else:
            success_rate, failure_rate = calculate_rates(
                success_total, failure_total, total_total)
    else:
        # Calculate rates normally if no off-peak time is specified
        success_rate, failure_rate = calculate_rates(
            success_total, failure_total, total_total)

    # Calculate TPS
    max_tps = calculate_tps(timestamps_combined)

    # Print the results in the required format
    print(f"{zabbix_hostname} {service_name}.success.rate {success_rate:.2f}")
    print(f"{zabbix_hostname} {service_name}.success.request {success_total}")
    print(f"{zabbix_hostname} {service_name}.total.request {total_total}")
    print(f"{zabbix_hostname} {service_name}.failed.request {failure_total}")
    print(f"{zabbix_hostname} {service_name}.failed.rate {failure_rate:.2f}")
    print(f"{zabbix_hostname} {service_name}.tps.rate {max_tps}")


def is_within_offpeak(offpeak_start, offpeak_end):
    """Check if the current system time falls within the off-peak time."""
    # Get the current system time
    current_time = datetime.now().time()

    # Handle overnight ranges where the end time is before the start time (e.g., 23:00-02:00)
    if offpeak_start > offpeak_end:
        return current_time >= offpeak_start or current_time <= offpeak_end
    else:
        return offpeak_start <= current_time <= offpeak_end


# Helper functions to calculate rates and TPS
def calculate_rates(success, failure, total):
    if total == 0:
        success_rate = 0
        failure_rate = 0
    else:
        success_rate = (success / total) * 100
        failure_rate = (failure / total) * 100
    return success_rate, failure_rate


def calculate_tps(timestamps):
    tps = {}
    max_tps = 0

    # Count occurrences per second
    for timestamp in timestamps:
        if timestamp not in tps:
            tps[timestamp] = 0
        tps[timestamp] += 1

    # Find the max TPS
    if tps:
        max_tps = max(tps.values())

    return max_tps


if __name__ == "__main__":
    process_logs(
        service_name="recovery",
        log_file="/var/log/nginx/apipostdata.log",
        success_pattern=r"AmountCharging 200",
        total_pattern=r"AmountCharging",
        offpeak_time='none'
    )

    process_logs(
        service_name="lending",
        log_file="/var/log/nginx/apipostdata.log",
        success_pattern=r"EvdGenericRequest 200",
        total_pattern=r"EvdGenericRequest",
        offpeak_time='none'
    )

    process_logs(
        service_name="sms",
        log_file="/var/log/nginx/apipostdata.log",
        success_pattern=r"SendSms 200",
        total_pattern=r"SendSms",
        offpeak_time='none'
    )

    process_logs(
        service_name="auto",
        log_file="/var/log/nginx/apipostdata.log,
        success_pattern=r'notify.+200',
        total_pattern=r'notify',
        offpeak_time='00:00-09:00'
    )
