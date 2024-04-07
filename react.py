import argparse,os,re,json

parser = argparse.ArgumentParser()
parser.add_argument("--login_file",help="login java file",required=True)
parser.add_argument("--react_file",help="react java file",required=True)
parser.add_argument("--input_dir",help="input feature dir",required=True)
parser.add_argument("--output_dir",help="output feature dir",required=True)
parser.add_argument("--targets",help="target keywords",required=True)
parser.add_argument("--keyword",help="to added keywords",required=True)
parser.add_argument("--scan_keywords",help="to added keywords",required=True)
parser.add_argument("--ignored_features",help="feature file to be ingored",required=True)
parser.add_argument("--ignored_steps",help="steps to be ingored",required=True)
parser.add_argument("--ignored_files",help="files to be ingored",required=True)

args = parser.parse_args()
accounts = {}
defaults = {}

default_orgs = {"ENTERPRISE_USER":"340dojy4","NON_DEFAULT_USER_ORG1":"340dojy4","DEFAULT_USER_ORG1":"340dojy4","TEAMS_ADMIN_ORG1":"340dojy4","DEFAULT_USER_ORG3":"b28yccwr"}

contexts = ["forensics","workspace","admin","policies","reporting","lexid digital","caess","lists","kpi alerts"]
step_headers = ["then","given","but","when","and"]

def scan_feature(folder,keywords,scenarios,feature_res,add_keyword,scan_keywords,targets,ignored,filepath=None):
    for filename in os.listdir(folder):
        if filename not in [".", ".."]:
            file_path = folder + "/" + filename
            if os.path.isfile(file_path) and filename.find(".feature") > 0 and filename.lower().find("react") < 0 and not is_target(filename,ignored["files"]):
                ingored_scenario = True
                forensics_scenario = False
                feature_res[filename] = {}
                current_scenario = ""
                current_context = ""
                lines = open(file_path, "r", encoding="utf-8").readlines()
                output_lines = []
                for line in lines:
                    content = line.strip(" \n\t")
                    if content.find("Scenario:") == 0:
                        if not forensics_scenario and len(current_scenario) > 0:
                            if filename not in res:
                                res[filename] = []
                            res[filename].append(current_scenario)
                        scenarios.append(current_scenario)
                        current_scenario = content.split(":",1)[1].strip(" ")
                        ingored_scenario = False
                        if filename in ignored["features"] and current_scenario.lower().find("react") > 0:
                            ingored_scenario = True
                        forensics_scenario = False
                        current_context = ""
                    elif not ingored_scenario:
                        if len(content) > 0 and content.find("@container") < 0 and len(current_scenario) > 0 and content.find(" ")>0 and not content.startswith("#"):
                            step = find_item(content, step_headers)
                            content = content.split("#")[0].split(" ",1)[1]
                            if step and not is_target(step,ignored["steps"]):
                                if not is_target(step,["logged in"," login "]):
                                    context = match_item(content,contexts)
                                    if context:
                                        current_context  = context
                                    if step.find("I fill in the username as ") >= 0:
                                        account = step.split('"')[1]
                                        if current_scenario not in accounts:
                                            accounts[current_scenario] = []
                                        accounts[current_scenario].append(account)

                                elif step.find("I login with username as ") >= 0:
                                     account = step.split('"')[1]
                                     if current_scenario not in accounts:
                                         accounts[current_scenario] = []
                                     accounts[current_scenario].append(account)

                                elif step.find(("I have logged in portal successfully using configured \"")) >=0:
                                    default = step.split('"')[1]
                                    if current_scenario not in defaults:
                                        defaults[current_scenario] = []
                                    defaults[current_scenario].append(default)

                                content = re.sub("\"([^\"]*)\"","{}",content)
                                if content.lower() in keywords or is_target(step.lower(),targets):
                                    if current_context in  ["","forensics"]:
                                        if current_scenario not in feature_res[filename]:
                                            feature_res[filename][current_scenario] = []
                                        feature_res[filename][current_scenario].append(content)
                                        if not forensics_scenario:
                                            output_lines.append("\tThen " + add_keyword + "\n")
                                        forensics_scenario = True
                                    else:

                                        feature_file = filename
                                        if filepath:
                                            feature_file = filepath + "/" + feature_file
                                        print("current context : " + feature_file + "->" + current_scenario +"->" + current_context + "| keyword : " + content)
                                else:
                                    for scan_keyword in scan_keywords:
                                        if content.lower().find(scan_keyword) >= 0:
                                            current_context = ""
                                            forensics_scenario = False
                    output_lines.append(line)
                if len(feature_res[filename]) == 0:
                    feature_list.append(filename)
                else:

                    output_file = output_dir
                    if filepath:
                        output_file += "/" + filepath
                    if not os.path.exists(output_file):
                        os.mkdir(output_file)
                    output_file += "/" +filename
                    outputFile = open(output_file, "w",encoding="utf-8")
                    outputFile.writelines(output_lines)
                    outputFile.close()

            elif os.path.isdir(file_path):
                if filepath:
                    filename = filepath + "/" + filename
                scan_feature(file_path,keywords,scenarios,featur_res,add_keyword,scan_keywords,targets,ignored,filepath=filename)

def is_target(content, targets):
    for target in targets:
        if content.lower().find(target) >= 0:
            return True
    return False


def find_item(content,items):
    if content.split(" ")[0].lower() in items:
        return content

def match_item(content,items):
    for item in items:
        if content.lower().find(item) >=0:
            return item


def update_feature(filename,login_keywords,scan_keywords,keyword,output_dir):
    current_scenario = ""
    lines = open(filename, "r", encoding="utf-8").readlines()
    output_lines =[]
    updated = []
    inject_keyword = False
    for line in lines:
        pre_inject = inject_keyword
        inject_keyword = False
        content = line.strip(" \n\t")
        if content.find("Scenario:") == 0:
            current_scenario = content.split(":",1)[1].strip(" ")
        else:
            if len(content) > 0 and content.find("@container") < 0 and len(current_scenario) > 0 and content.find(
                    " ") > 0 and not content.startswith("#"):

                if content.lower().find("i login with username as") >= 0:
                    print(content)
                content = content.split("#")[0].split(" ", 1)[1]
                content = re.sub("\"([^\"]*)\"", "{}", content)
                if content.lower() in login_keywords and content.find("log out") < 0:
                    inject_keyword = True
                    updated.append(current_scenario)
                else:
                    for scan_keyword in scan_keywords:
                        if content.lower().find(scan_keyword.lower()) >= 0:
                            inject_keyword = True
                            updated.append(current_scenario)
                            break
        if not inject_keyword and pre_inject and current_scenario not in scenarios:
            output_lines.append("\tThen " + keyword + "\n")
        output_lines.append(line)
    feature_file = os.path.basename(filename)
    output_file = output_dir + "\\" + feature_file
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    output_feature = open(output_file,"w",encoding="utf-8")
    output_feature.writelines(output_lines)
    output_feature.close()



def extract_keywords(java_file,res):
    lines = open(java_file, "r", encoding="utf-8").readlines()
    current_keyword = ""
    for line in lines:
        content = line.strip(" \n\t")
        if line.find("@Then") >= 0 or line.find("@Given") >= 0 or line.find("@And") >= 0 or line.find(
                "@When") >= 0 or line.find("@But") >= 0:
            current_keyword = content.split("(", 1)[1].replace('\\"([^\\"]*)\\"', "{}").replace("{string}", "{}") \
                .replace('\"{int}\"', "{}").replace("{int}", "{}").replace('\"{word}\"', "{}").rsplit(")", 1)[0].strip(
                "\"$^").lower()
        else:
            if line.find("=") < 0 and line.find("class") < 0 and (
                    line.find("public ") >= 0 or line.find("public static void ") >= 0 or line.find("private") >= 0):
                function = content.split("(", 1)[0].rsplit(" ", 1)[1]
                if len(current_keyword) > 0:
                    res[current_keyword] = function
                    current_keyword=""



if __name__ == "__main__":
    react_files = args.react_file.split("|")
    login_file = args.login_file
    input_dir = args.input_dir
    output_dir = args.output_dir
    ignored_features = args.ignored_features.split("|")
    ignored_files = args.ignored_files.split("|")
    ignored_steps = args.ignored_steps.split("|")
    ignored = {}
    ignored["features"] = ignored_features
    ignored["steps"] = ignored_steps
    ignored["files"] = ignored_files
    feature_list = []
    featur_res = {}
    forensics_keywords = {}
    login_keywords = {}
    for react_file in react_files:
        extract_keywords(react_file,forensics_keywords)
    extract_keywords(login_file,login_keywords)
    scan_keywords = args.scan_keywords.split("|")
    add_keyword = args.keyword

    # for keyword in login_keywords:
    #     print(keyword)

    gwt_keywords = {}
    react_keywords = {}

    for keyword in forensics_keywords:
        if forensics_keywords[keyword].lower().find("react") >= 0 or keyword.lower().find("react") >= 0:
            react_keywords[keyword] = True
        else:
            gwt_keywords[keyword] = False
    # keywords[keyword] = False

    for keyword in react_keywords:
        gwt_keyword = keyword.replace(" in react","").replace(" react","").replace("react ","").replace("react","").replace("  "," ")
        # if gwt_keyword.find("has been saved as a recent search") > 0:
        #     print(gwt_keyword)

        if gwt_keyword in gwt_keywords:
            gwt_keywords[gwt_keyword] = keyword
        # else:
        #     print("Not found : " + gwt_keyword + "|" + keyword)
    not_implemented_list = []
    for gwt in gwt_keywords:
        if not gwt_keywords[gwt]:
            not_implemented_list.append(gwt)
            print(gwt)
    # print("gwt functions : " + str(len(gwt_keywords)) )

    # print("not implemented funcs :" + str(len(not_implemented_list)))
    res={}
    # for func in not_implemented_list:
    #     print(func)
    targets = args.targets.split("|")
    scenarios = []
    scan_feature(input_dir,forensics_keywords,scenarios,featur_res,add_keyword,scan_keywords,targets,ignored)

    # target =args.target
    # update_feature(target,login_keywords,scan_keywords,add_keyword,output_dir)
    # for feature in res:
    #     print(feature + ":" + str(len(res[feature])))
    #
    output_file = open(output_dir +"/react.json","w",encoding="utf-8")
    summary = 0
    for key in featur_res:
        summary += len(featur_res[key])

    json.dump(featur_res,output_file,indent=4)
    output_file.close()

    orgs_file = open("orgs.json", "r", encoding="utf-8")

    s_org = json.load(orgs_file)

    orgs_file.close()

    res = {"others":{}}
    for feature in featur_res:
        for scenario in featur_res[feature]:
            if scenario in s_org:
                org = s_org[scenario]
                if org not in res:
                    res[org] = {}
            else:
                org="others"

            res[org][scenario] = {}
            res[org][scenario]["feature"] = feature
            res[org][scenario]["steps"] = featur_res[feature][scenario]



    account_json = open("user_accounts.json","r",encoding="utf-8")
    user_accounts = json.load(account_json)
    account_json.close()
    accounts_org = {}
    for user_account in user_accounts:
        accounts_org[user_account["id"]] = user_account["default_org_id"]
    others = 0
    account_list = []
    default_list = []



    for scenario in accounts:
        if scenario in res["others"]:
            if "accounts" not in res["others"][scenario]:
                res["others"][scenario]["accounts"] = accounts[scenario]
                others += 1
                for account in accounts[scenario]:
                    if account not in account_list:
                        account_list.append(account)
    for scenario in defaults:
        if scenario in res["others"]:
            if "defaults" not in res["others"][scenario]:
                res["others"][scenario]["defaults"] = defaults[scenario]
                others += 1
                for default in defaults[scenario]:
                    if default not in default_list:
                        default_list.append(default)

    # for scenario in res["others"]:
    #     if "accounts" in res["others"][scenario]:
    #         for account in res["others"][scenario]["accounts"]:
    #             org_id = accounts_org[account]
    #             if org_id not in res:
    #                 res[org_id] = {}
    #             res[org_id][scenario] = res["others"][scenario]
    #     if "defaults" in res["others"][scenario]:
    #         for default in res["others"][scenario]["defaults"]:
    #             org_id = default_orgs[default]
    #             if org_id not in res:
    #                 res[org_id] = {}
    #             res[org_id][scenario] = res["others"][scenario]

    for org in res:
        print(org + ":" + str(len(res[org])))


    print(str(others))
    for scenario in res["others"]:
        if "accounts" not in res["others"][scenario] and "defaults" not in res["others"][scenario]:
            print(scenario)

    res_file = open("scenarios.json","w",encoding="utf-8")

    json.dump(res,res_file,indent=4)

    res_file.close()

    print(account_list)
    print(default_list)
