import SSHLibrary
import argparse

class ServerLog:
    def __init__(self, server, username, private_key):
        self.sshclient = SSHLibrary.SSHLibrary()
        self.sshclient.open_connection(server)
        self.login_output = self.sshclient.login_with_public_key(username,private_key)

    def set_duration(self, start_time,end_time):
        self.test_date, start_hour = start_time.split("T")
        end_hour = end_time.split("T")[1]
        self.match_str = self.test_date + "T("
        for hour in range(int(start_hour), int(end_hour) + 1):
            self.match_str += str(hour).zfill(2) + ":[0-5][0-9]:[0-5][0-9]|"
        self.match_str = self.match_str.strip("|")
        self.match_str += ")"

    def extract_log(self, log_name,log_files,keyword,exclude=None):
        log_name = log_name.replace("<date>",self.test_date)
        log_files = log_files.replace("<date>",self.test_date)
        if exclude:
            command = "zstdgrep -E \"" + self.match_str + "\" " + log_files + "|grep -i " + keyword + "|grep -iv "+ exclude + ">" + log_name + ".log"
        else:
            command = "zstdgrep -E \"" + self.match_str + "\" " + log_files + "|grep -i " + keyword + ">" + log_name + ".log"
        ret = self.sshclient.execute_command(command)
        if len(ret) == 3 and not ret[2] == 0:
            print(ret)
        else:
            self.sshclient.get_file( log_name + ".log")

    def __del__(self):
        self.sshclient.close_connection()





if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server",help="log server name",required=True)
    parser.add_argument("--username",help="username log in server",required=True)
    parser.add_argument("--private_key", help="private_key location",required=True)
    parser.add_argument("--start_time", help="start time date and hours, format is YYYY-MM-DDTHH ",required=True)
    parser.add_argument("--end_time",help="end time date and hours, format is YYYY-MM-DDTHH",required=True)
    parser.add_argument("--log_map", help="server,logfile pattern,grep keyword group, delimiter as |",required=True)

    args = parser.parse_args()
    server = args.server
    private_key = args.private_key
    start_time = args.start_time
    end_time = args.end_time
    username = args.username
    log_maps=args.log_map.split("|")

    log_dict={}
    server_log = ServerLog(server,username,private_key)
    server_log.set_duration(start_time,end_time)


    for log_map in log_maps:
        log_name, log_pattern, keyword = log_map.split(":",2)
        server_log.extract_log(log_name,log_pattern,keyword)
