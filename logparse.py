import hashlib
import os.path,json
import re

cfg = {"dwh":"data","crypto":"crypto","iam":"iam","report":"report","policy":"policy","case":"cm","cm":"cm","otin":"otin"}
email_validate_pattern = r"^[a-z0-9_-]+(?:\.[a-z0-9_-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"

log_def = {"PortalCasAuthenticationProvider.java":"session","GwtRestValidatorAdvice.java":"worker",
 "GeneralRestServiceImpl.java":"genernal"}

def email_char(char):
    if char < 48 or ( char > 57 and char < 65) or ( char > 90 and char < 97 ) or char > 122:
        return False
    return True

def getEmail(line):
    new_line = line
    if line.lower().find("user ") > 0:
        new_line = line.lower().split("user ",1)[1]
    if new_line.find("@") < 0 and line.lower().find("userid") >  0:
        new_line =  line.lower().split("userid",1)[1]
    if new_line.find("@") > 0:
        left, right = new_line.split("@", 1)
        left = left.rsplit(":",1)[-1].rsplit("/",1)[-1].rsplit("=",1)[-1].rsplit(",",1)[-1]
        left= left.split("FRAUD_",1)[-1].split("FCC_",1)[-1]
        right = right.split(":",1)[0].split("/",1)[0].split(",",1)[0]
        email = left.rsplit(" ", 1)[-1] + "@" + right.split(" ", 1)[0]
        try:
            s = 0
            while not email_char(ord(email[s])):
                s += 1
            e = len(email)
            while not email_char(ord(email[e - 1])):
                e -= 1
            email = email[s:e]
        except Exception as e:
            print(e)
        if email.find("@") > 0:
            return email
    else:
        print(line)

# stacks = {}
# errors = {}
# error_stack = []
# alerts ={}
# error_nos = {}
# stack_start = -1
# code_start = -1
# error_list = []
# warn_list = []
# threads = {}
# is_stack = False
# jobs = {}
# current_error = None
# current_stack = None
# current_users = {}
# thread_no  = None
# log_infos = {}
# log_units = {}
# current_stack_error = None
# current_session = {}
# sessions = {}



class PortalLogParser:
    def __init__(self, log_file, test_date):
        self.log_file = log_file
        logFile = open(self.log_file, "r", encoding="utf-8")
        self.lines = logFile.readlines()
        logFile.close()
        self.log_cfg = {"dwh":"data","crypto":"crypto","iam":"iam","report":"report","policy":"policy","cas":"cas","clientexception":"portal","cm":"cm","insufficientprivilegeexception":"portal","internalsystemexception":"portal"}
        self.threads = {}
        self.current_error = None
        self.errors = {}
        self.error_list = []
        self.stacks = {}
        self.current_stack = None
        self.issue_list = {}
        self.session_list = []
        self.current_stack_index = None
        self.test_date = test_date
        self.current_users = {}
        self.log_units = {}
        self.current_session = {}
        self.thread_no = None
        self.sessions = {}
        self.categories = {}
        self.current_job = None
        self.current_error_index = None
        self.current_stack_error = None
        self.error_stack = []
        self.jobs={}
        self.others=[]

    def setupThread(self, line,line_no):
        if len(line.split(" [")) >= 2 and line.find(self.test_date) > 0:
            self.thread_no = line.split(" [")[1].split("] ")[0]
            if self.thread_no not in self.threads:
                self.threads[self.thread_no] = []
            self.threads[self.thread_no].append(line_no)

    def matchUserTime(self, user_sessions, user_time,scenario):
        for start_time in user_sessions:
            startTime = start_time.replace("T", " ")
            if user_time["start_time"] < startTime and user_time["end_time"] > startTime:
                user_sessions[start_time]["scenario"] = scenario["name"]
                if "session_ids" not in scenario:
                    scenario["session_ids"]  = []
                scenario["session_ids"].append(user_sessions[start_time]["id"])
                return user_sessions[start_time]

    def setScenario(self, scenario):
        for user in scenario["test_users"]:
            session_user = user.lower()
            if session_user in self.sessions:
                user_sessions = self.sessions[session_user]
                if type(scenario["test_users"][user]) == dict:
                    current_user_time = scenario["test_users"][user]
                    session = self.matchUserTime(user_sessions,current_user_time,scenario)
                    if not session:
                        print(scenario["test_users"][user])
                else:
                    for item in scenario["test_users"][user]:
                        session = self.matchUserTime(user_sessions,item,scenario)
                        if not session:
                            print(item)
            else:
                print(scenario)

    def setupException(self, line):
        exception = line.split("[m")[1]
        if exception.find(":") > 0 and self.current_error:
            print(exception)
            name, reason = exception.split(":", 1)
            name = name.strip(" ")
            reason = reason.strip(" ")
            if "stacks" not in self.current_error:
                self.current_error["stacks"] = {}
            if name not in self.current_error["stacks"]:
                self.current_error["stacks"][name] = {}
            self.current_error["stacks"][name] = {"name": reason}
            self.current_error_index = self.current_error["stacks"][name]
            if self.current_error["thread"] in self.errors:
                self.current_error["stacks"][name][len(self.errors[self.current_error["thread"]]["msg"])] = reason
            else:
                print(self.errors)
            self.current_stack_error = self.current_error
            if name not in self.stacks:
                self.stacks[name] = {}
            self.current_stack = self.stacks[name]
            return name

    def processError(self,line):
        if line.find("[m") > 0 and line.find("[info ") < 0:
            name = self.setupException(line)
        elif self.current_stack_error and line.find("Caused by: ") > 0:
            cause_by = line.split("Caused by: ")[1].split(":")[0]
            if "stacks" in self.current_stack_error:
                self.current_error_index["caused_by"] = cause_by
                self.current_stack_index = None
            else:
                print(self.current_stack_error)

        elif self.current_error_index and line.find(self.test_date) < 0 and (line.find("class") > 0 or line.find(
                "java") > 0 or line.find(".js") > 0):
            if "index" not in self.current_error_index:
                code_index = line.split(":",1)[-1].strip(" \n")
                self.current_error_index["index"] = code_index
                if code_index not in self.current_stack:
                    self.current_stack[code_index] = []
                    self.current_stack_index = self.current_stack[code_index]
                else:
                    self.current_stack_index = None
            if not self.current_stack_index == None:
                self.current_stack_index.append(line)

    def getThreadType(self, line, line_info):
        thread_type = ""
        if line.find("security.PortalCasAuthenticationProvider (line 56)") > 0:
            m = re.search("User ([^\s]*)", line)
            thread_type = "session"
            if m:
                line_info["user"] = m.group(1)
            else:
                print(line)

        elif line.find("service.SharedCommonService ") > 0:
            if line.find(" (line 348)") > 0:
                # thread_type = "job"
                if self.thread_no in self.log_units:
                    self.log_units[self.thread_no]["jobs"] = []
                    self.current_job = self.log_units[self.thread_no]
                    if not self.log_units[self.thread_no]["type"] == "job":
                        log_unit = self.log_units[self.thread_no]
                        log_unit["type"] = "job"
                        self.jobs[log_unit["start_time"]] = log_unit
                else:
                    print(line)
            elif line.find(" (line 354)") > 0:
                thread_type = "sub_job"

        # elif line.find("rest.GeneralRestServiceImpl (line 368)") > 0:
        #     m = re.search("user ([^\s]*)", line)
        #     thread_type = "general"
        #     if m:
        #         line_info["user"] = m.group(1)
        #     else:
        #         print(line)

        # elif line.find("service.PreferencesService (line 92)") > 0:
        #     thread_type = "preference"


        elif line.find("cache.PreferencesCacheService (line 53)") > 0:
            thread_type = "maintenance"
            m = re.search("key ([^\s]*)", line)
            if m:
                line_info["user"] = "_".join(m.group(1).split("_")[2:])
            else:
                print(line)

        elif line.find("validation.GwtRestValidatorAdvice (line 99)") > 0:
            thread_type = "worker"
            line_info["name"] = line.rsplit(" ",1)[-1].strip("\n")

        elif line.find("controller.PortalUIClientController (line 166)") > 0:
            thread_type = "worker"
            line_info["name"] = "getIndexPageStartElements"

        elif line.find("featurepermission.FeaturePermissionAdvice (line 148)") > 0 and (self.thread_no not in self.log_units or \
                not len(self.threads[self.thread_no]) - 2 == self.log_units[self.thread_no]["start"]):
            if self.thread_no not in self.log_units:
                print(line)
            thread_type = "worker"
            m = re.search("user ([^\s]*), org/cus id ([^\s]*), isCustomer = ([^\s]*)\. .*execution\(([^\(]+)", line)
            if m:
                login = m.group(1)
                line_info["user"] = login
                line_info["name"] = m.group(4)
                if self.thread_no not in self.current_users or not self.current_users[self.thread_no]["login"] == login:
                    self.current_users[self.thread_no] = {"login": login}
                self.current_users[self.thread_no]["start"] = len(self.threads[self.thread_no]) - 1
                if m.group(3) == "false":
                    line_info["org"] = m.group(2)
                    self.current_users[self.thread_no]["org"] = m.group(2)
                elif m.group(3) == "true":
                    line_info["customer"] = m.group(2)
                    self.current_users[self.thread_no]["customer"] = m.group(2)


        if "user" not in line_info and line.find("@") > 0:
            email = getEmail(line)
            if email:
                line_info["user"] = email

        if "user" in line_info:
            if self.thread_no not in self.current_users or (not self.current_users[self.thread_no]["login"] == line_info["user"] and
                                    line_info["user"] in self.current_session):
                self.current_users[self.thread_no] = {"login":line_info["user"]}
                if self.thread_no not in self.log_units:
                    start_time = self.test_date + line.split(self.test_date)[1].split(" ")[0]
                    self.log_units[self.thread_no] = {"type":"others", "user":line_info["user"], "start":0, "thread":self.thread_no, "start_time":start_time}
            if self.thread_no in self.log_units:
                log_unit = self.log_units[self.thread_no]
                if log_unit["type"] == "worker" and "user" not in log_unit:
                    log_unit["user"] = line_info["user"]
                    if line_info["user"] in self.current_session:
                        self.current_users[self.thread_no]["login"] = line_info["user"]
                        if "workers" not in self.current_session[log_unit["user"]]:
                            print(self.current_session[log_unit["user"]])
                        else:
                            self.current_session[log_unit["user"]]["workers"].append(log_unit)
                        log_unit["id"] = len(self.current_session[log_unit["user"]]["workers"])
                    else:
                        session_unit = {"user": log_unit["user"], "type": "session",
                                            "start_time": log_unit["start_time"], "fake": True, "workers": [],
                                            "jobs": []}
                        self.session_list.append(session_unit)
                        session_unit["id"] = len(self.session_list)
                        self.current_session[session_unit["user"]] = session_unit
                        self.current_session[log_unit["user"]]["workers"].append(log_unit)
                        log_unit["id"] = len(self.current_session[log_unit["user"]]["workers"])

        return thread_type

    def parseError(self, line):
        if line.find("31mERROR ") > 0 or line.find("33mWARN ") > 0:
            level = "ERROR"
            if line.find("33mWARN") > 0:
                level = "WARN"

            if self.thread_no: # and self.thread_no not in self.errors:
                if self.thread_no in self.log_units and "user" in self.log_units[self.thread_no] \
                        and self.log_units[self.thread_no]["user"] in self.current_session:
                    # user = self.current_users[self.thread_no]["login"]
                    user = self.log_units[self.thread_no]["user"]
                        # self.errors[self.thread_no] = {"msg": [], "level": level, "thread": self.thread_no,
                        #                                "session": self.current_session[user]["id"]}
                    if "errors" not in self.current_session[user]:
                        self.current_session[user]["errors"] = {}
                    if self.thread_no in self.log_units:
                        log_unit = self.log_units[self.thread_no]
                    else:
                        print(self.thread_no)
                    if "id" in log_unit:
                        if log_unit["id"] not in self.current_session[user]["errors"]:
                    # if self.thread_no not in self.current_session[user]["errors"]:
                            self.current_session[user]["errors"][log_unit["id"]] = {"msg": [], "level": level, "thread": self.thread_no,
                                                                            "session": self.current_session[user][
                                                                                "id"], "log":log_unit["id"]}
                            self.error_list.append(self.current_session[user]["errors"][log_unit["id"]])
                            self.current_session[user]["errors"][log_unit["id"]]["id"] = len(self.error_list)


                        self.errors[self.thread_no] = self.current_session[user]["errors"][log_unit["id"]]
                        if "name" in log_unit:
                            self.errors[self.thread_no]["name"] = log_unit["name"]
                    else:
                        print(log_unit)
                        if "others" not in self.current_session[user]["errors"]:
                            self.current_session[user]["errors"]["others"] = {}
                        if log_unit["type"] not in self.current_session[user]["errors"]["others"]:
                            self.current_session[user]["errors"]["others"][log_unit["type"]] = {"msg": [], "level": level, "thread": self.thread_no,
                                                                            "session": self.current_session[user][
                                                                                "id"]}
                        self.errors[self.thread_no] = self.current_session[user]["errors"]["others"][log_unit["type"]]
                    if "level" not in self.current_session[user] or self.current_session[user]["level"] == "WARN":
                        self.current_session[user]["level"] = level
                    # if "errors" not in self.current_session[user]:
                    #     self.current_session[user]["errors"] = []
                    # self.current_session[user]["errors"].append(self.errors[self.thread_no])
                    if "start" in self.current_users[self.thread_no] and len(self.errors[self.thread_no]["msg"]) == 0:
                        self.errors[self.thread_no]["user"] = self.current_users[self.thread_no]
                        for i in range(self.current_users[self.thread_no]["start"], len(self.threads[self.thread_no])):
                            self.errors[self.thread_no]["msg"].append(self.lines[self.threads[self.thread_no][i]])
                    else:
                        self.errors[self.thread_no]["msg"].append(line)
                else:
                    print(line)

                    self.errors[self.thread_no] = {"msg": [], "level": level, "thread": self.thread_no}
                    self.errors[self.thread_no]["msg"].append(line)
                    self.others.append(self.errors[self.thread_no])
                self.error_stack.append(self.thread_no)
            elif self.thread_no and self.thread_no in self.errors:
                self.errors[self.thread_no]["msg"].append(line)

            # if level == "ERROR":
            #     self.errors[self.thread_no]["level"] = level
            self.current_error = self.errors[self.thread_no]
            if line.find("error-uuid:") > 0:
                info = line.split("error-uuid:")[1].split("[")[0].strip(" ")
                items = info.split(",")
                uuid = items[0].strip(" ")
                self.current_error["uuid"] = uuid
                for item in items[1:]:
                    values = item.split("=")
                    if len(values) == 2:
                        if item.find("user") > 0:
                            self.current_error["user_id"] = values[1].strip(" ")
                        elif item.find("customer") > 0:
                            self.current_error["customer"] = values[1].strip(" ")
                        elif item.find("org=") > 0:
                            self.current_error["org"] = values[1].strip(" ")
                    else:
                        print(line)

        # else:
        #     if self.thread_no and self.thread_no in self.errors:
        #         error = self.errors.pop(self.thread_no)
        #         self.error_stack.remove(self.thread_no)
        #         if len(self.error_stack) > 0:
        #             self.current_error = self.errors[self.error_stack[-1]]
        #         self.error_list.append(error)
        #         error["id"] = len(self.error_list)

    def processThread(self, line, line_no, thread_type, line_info):
        log_start = len(self.threads[self.thread_no]) - 1
        if self.thread_no in self.log_units:
            log_unit = self.log_units.pop(self.thread_no)
            log_start = None
            if thread_type == "worker" or thread_type == "preference":
                log_unit["end"] = len(self.threads[self.thread_no]) - 2

            elif thread_type == "session":
                log_unit["end"] = len(self.threads[self.thread_no]) - 5

            elif thread_type == "job" or thread_type == "sub_job":
                log_unit["end"] = len(self.threads[self.thread_no]) - 2

            elif thread_type == "general":
                log_unit["end"] = len(self.threads[self.thread_no]) - 8
            elif thread_type == "maintenance":
                if log_unit["type"] == "maintenance":
                    self.log_units[self.thread_no] = log_unit
                    return
                else:
                    log_unit["end"] = len(self.threads[self.thread_no]) - 2

            if "end" in log_unit:
                log_unit["msg"] = []
                for i in range(log_unit["start"],log_unit["end"] + 1):
                    log_unit["msg"].append(self.lines[self.threads[log_unit["thread"]][i]])
                log_start = log_unit["end"] + 1
            else:
                print(log_unit)

            if not log_unit["type"] == "maintenance":
                start_time = log_unit["start_time"]
                if log_unit["type"] == "session":
                    user = log_unit["user"]
                    if log_unit["user"] in self.current_session:
                        user_session = self.current_session.pop(log_unit["user"])
                        self.current_session[log_unit["user"]] = log_unit
                        if not user_session["user"] in self.sessions:
                            self.sessions[user_session["user"]] = {}
                        self.sessions[log_unit["user"]][start_time] = user_session
                # elif log_unit["type"] == "job":
                #     self.jobs[start_time] = log_unit
                elif log_unit["type"] == "sub_job":
                    if "user" not in log_unit:
                        print(log_unit)

        if self.thread_no not in self.log_units:
            self.log_units[self.thread_no] = {"thread": self.thread_no, "start": log_start}
        log_unit = self.log_units[self.thread_no]
        log_unit["type"] = thread_type
        if not thread_type == "maintenance":
            log_unit["start_time"] = self.test_date + line.split(self.test_date)[1].split(" ")[0]
            for key in line_info:
                log_unit[key] = line_info[key]
        else:
            if "user" in line_info and line_info["user"] in self.current_session:
                if "maintenance" not in self.current_session[line_info["user"]]:
                    self.current_session[line_info["user"]]["maintenance"] = self.lines[line_no]
                else:
                    print(self.current_session[line_info["user"]])
            else:
                print(line_info)

        if thread_type == "session":
            user = log_unit["user"]
            if user in self.current_session and "fake" in self.current_session[user] and self.current_session[user][
                "start_time"] > log_unit["start_time"]:
                self.current_session[user].pop("fake")
                for key in log_unit:
                    self.current_session[user][key] = log_unit[key]
                self.log_units[self.thread_no] = self.current_session[user]
            else:
                log_unit["workers"] = []
                log_unit["jobs"] = []
                self.session_list.append(log_unit)
                log_unit["id"] = len(self.session_list)
                self.current_session[log_unit["user"]] = log_unit
                self.current_users[self.thread_no] = {"login":log_unit["user"]}
        # elif thread_type == "worker":
        #     if "user" in log_unit and "id" not in log_unit:
        #         user = log_unit["user"]
        #         if user == 'cucumber-cm-user10@threatmetrix.com':
        #             print(log_unit)
        #
        #     else:
        #         print(log_unit)
        # elif thread_type == "job":
        #     self.current_job = log_unit
        #     log_unit["jobs"] = []
        elif thread_type == "sub_job":
            self.current_job["jobs"].append(log_unit)
        elif thread_type == "genernal":
            if "genernal" not in self.current_session[log_unit["user"]]:
                self.current_session[log_unit["user"]]["genernal"] = log_unit
            else:
                print(self.current_session[log_unit["user"]])


    def processSubJob(self, line):
        if self.thread_no in self.log_units and self.log_units[self.thread_no]["type"] == "sub_job":
            if "user" not in self.log_units[self.thread_no] and line.find("@") > 0:
                email = getEmail(line)
                if email:
                    self.log_units[self.thread_no]["user"] = email
                    if email in self.current_session:
                        self.current_session[email]["jobs"].append(self.log_units[self.thread_no])
                        self.log_units[self.thread_no]["id"] = "job_" + str(len(self.current_session[email]["jobs"]))

    def getSessions(self):
        for user in self.current_session:
            user_session = self.current_session[user]
            start_time = user_session["start_time"]
            if not user in self.sessions:
                self.sessions[user] = {}
            self.sessions[user][start_time] = user_session

    def getErrors(self):
        for thread_no in self.errors:
            error = self.errors[thread_no]
            self.error_list.append(error)
            error["id"] = len(self.error_list)


        for error in self.error_list:
            if error["level"]  == "ERROR":
                if "user_id" not in error:
                    if "user" in error:
                        error["user_id"] = error["user"]["login"]
                    else:
                        users = re.findall(email_validate_pattern,error["msg"][0])
                        if users:
                            error["user_id"] = users[0].strip(",:].")

                if "org" not in error and "user" in error and "org" in error["user"]:
                    error["org"] = error["user"]["org"]
                if len(error["msg"]) > 0:
                    index = error["msg"][0].find(self.test_date)
                    error["start_time"] = error["msg"][0][index:index + 23]
                    index = error["msg"][-1].find(self.test_date)
                    error["end_time"] = error["msg"][-1][index:index + 23]

                if "user_id" in error:
                    if error["user_id"] not in self.issue_list:
                        self.issue_list[error["user_id"]] = {}
                    self.issue_list[error["user_id"]][error["start_time"]] = error
                else:
                    print(error)
                if "stacks" not in error:
                    error_msg = ("").join(error["msg"])
                    print(error_msg)



    def parseLog(self):
        for line_no in range(len(self.lines)):
            line = self.lines[line_no]
            if line.find("k8s-worker118.qa2.sac: \x1b[m\x1b[33mWARN  [qtp930230451-1954] 2023-12-10T09:10:23,170 SharedCommonService.java service.SharedCommonService (line 481) Tmx column does not exist for: event_datetime due to No enum constant com.threatmetrix.ccc.portal.shared.common.TmxColumn.EVENT_DATETIME") >= 0:
                print(line)
            self.setupThread(line,line_no)
            if line.find(self.test_date) < 0 :
                self.processError(line)
            else:
                line_info = {}
                thread_type = self.getThreadType(line,line_info)
                self.parseError(line)
                if "user" in line_info and line_info["user"] == 'cucumber-cm-user10@threatmetrix.com':
                    print(line_info)

                if not thread_type == "":

                    self.processThread(line,line_no,thread_type,line_info)

                    # errors[thread_no]["msg"].append(line)
                else:
                    self.processSubJob(line)
            if self.thread_no in self.current_users and self.current_users[self.thread_no]["login"].find("@") < 0:
                print(line)

        self.getSessions()
        self.getErrors()
        self.processCategories()
        self.dumpStacks()

    def dumpStacks(self):
        folder = self.log_file.split(".")[0]
        if not os.path.exists(folder):
            os.mkdir(folder)

        stackFile = folder + "/stacks.json"
        stack_file = open(stackFile,"w", encoding="utf-8")
        json.dump(self.stacks,stack_file,indent=4)
        stack_file.close()


    def dumpSession(self, session):
        folder = self.log_file.split(".")[0]
        if not os.path.exists(folder):
            os.mkdir(folder)
        session_id = session["id"]
        folder += "/" + str(session_id)
        if not os.path.exists(folder):
            os.mkdir(folder)

        if "thread" in session:
            thread_file = folder + "/session.log"
            self.dumpThread(session,thread_file)


        for worker in session["workers"]:
            index = worker["id"]
            worker_file = folder + "/worker_" + str(index) + ".log"
            self.dumpThread(worker,worker_file)
        for job in session["jobs"]:
            index = job["id"]
            job_file = folder + "/" + str(index) + ".log"
            self.dumpThread(job,job_file)
        json_file = folder + "/session.json"
        jsonFile = open(json_file, "w",  encoding="utf-8")
        json.dump(session,jsonFile,indent=4)
        jsonFile.close()


    def dumpThread(self, thread, file_name):
        if "msg" in thread:
            thread.pop("msg")
        else:
            print(thread)
        threadFile = open(file_name, "w", encoding="utf-8")
        thread_lines = []
        end = len(self.threads[thread["thread"]])
        if "end" in thread:
            end = thread["end"] + 1
        for i in range(thread["start"], end):
            thread_lines.append(self.lines[self.threads[thread["thread"]][i]])
        threadFile.writelines(thread_lines)
        threadFile.close()

    def assignCategory(self, error):
        if error["level"] == "ERROR":
            category = None
            if "name" in error:
                category  = self.findCategory(error["name"])
            if not category:
                if "stacks" in error:
                    for stack in error["stacks"]:
                        if "caused_by" not in error["stacks"][stack] or error["stacks"][stack][
                            "caused_by"] not in self.stacks:
                            category = self.findCategory(stack)

                        else:
                            name = error["stacks"][stack]["caused_by"]
                            category = self.findCategory(name)
                        if not category:
                            if "index" in error["stacks"][stack]:
                                index = error["stacks"][stack]["index"]
                                category = self.findCategory(index)
                            else:
                                print(error)
                        if category:
                            break

            if not category:
                msg_i = -1

                while msg_i + len(error["msg"]) >= 0:
                    last_msg = error["msg"][msg_i]
                    if last_msg.find("31mERROR") > 0:
                        index = last_msg.find(self.test_date)
                        api = last_msg[index + 23:].split(".java")[0].strip(" ")
                        category = self.findCategory(api)
                        if category:
                            break
                    msg_i -= 1

            if not category:
                category = "others"
            errors = self.categories[category]["errors"]
            if "name" in error:
                if error["name"] not in errors:
                    errors[error["name"]] = []
                errors[error["name"]].append(error)
            else:
                errors["others"].append(error)

    def findCategory(self, target):
        for key in cfg:
            if target.lower().find(key) >= 0:
                if cfg[key] not in self.categories:
                    self.categories[cfg[key]] = {"errors": {"others": []}}
                return cfg[key]


    def processCategories(self):
        self.categories = {"others":{"errors":{"others":[]}}}
        for user_name in self.sessions:
            for start_time in self.sessions[user_name]:
                if "level" in self.sessions[user_name][start_time] and self.sessions[user_name][start_time]["level"] == "ERROR":
                    error_session = self.sessions[user_name][start_time]
                    for error_id in error_session["errors"]:
                        if not error_id == "others":
                            error = error_session["errors"][error_id]
                            if "user" not in error:
                                error["user"] = user_name
                            self.assignCategory(error)
                        elif "others" in error_session["errors"]:
                            for error_id in error_session["errors"]["others"]:
                                error = error_session["errors"]["others"][error_id]
                                if "user" not in error:
                                    error["user"] = user_name
                                self.assignCategory(error)
                    print(user_name + ":" + start_time)
    # if "stacks" in issue:
    #     for name in issue["stacks"]:
    #         print(name + ":" + str(issue["stacks"][name]))

if __name__ == "__main__":
    portalLog = PortalLogParser("qa1_portal.log","2024-01-09")
    portalLog.parseLog()
    for user in portalLog.sessions:
        for start_time in portalLog.sessions[user]:
            session = portalLog.sessions[user][start_time]
            if "level" in session and session["level"] == "ERROR":
                portalLog.dumpSession(session)
    print(portalLog.errors)
