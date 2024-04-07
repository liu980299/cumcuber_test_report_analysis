import argparse,json,re
import datetime
import os

def scan_feature(folder):
    for filename in os.listdir(folder):
        if filename not in [".", ".."]:
            file_path = folder + "/" + filename
            if os.path.isfile(file_path) and filename.find(".feature") > 0:
                feature_list.append(filename)
                current_scenario = ""
                lines = open(file_path,"r",encoding="utf-8").readlines()
                for line in lines:
                    content = line.strip(" \n\t")
                    if content.find("Scenario:") == 0:
                        current_scenario = content.split(":",1)[1].strip(" ")
                    else:
                        if len(content) > 0 and content.find("@container") < 0 and len(current_scenario) > 0 and content.find(" ")>0:
                            content = content.split(" ",1)[1]
                            if content in res:
                                org = res[content]
                                if current_scenario not in scenario_list:
                                    scenario_list.append(current_scenario)
                                if org not in org_s:
                                    org_s[org] = []
                                if current_scenario not in org_s[org]:
                                    org_s[org].append(current_scenario)

            elif os.path.isdir(file_path):
                scan_feature(file_path)


def get_org(function, stack):
    if function in orgs:
        return orgs[function]
    elif function in functions:
        for statement in functions[function]:
            if statement not in stack and get_org(statement,[*stack,statement]):
                return get_org(statement,[*stack,statement])

parser = argparse.ArgumentParser()
parser.add_argument("--login_file",help="login java file",required=True)
parser.add_argument("--input_dir",help="input feature dir",required=True)

# parser.add_argument("--output_dir",help="output feature dir",required=True)
args = parser.parse_args()

if __name__ == "__main__":
    input_dir = args.input_dir
    login_file = open(args.login_file,"r",encoding="utf-8")
    lines = login_file.readlines()
    keywords = {}
    functions= {}
    current_keyword = ""
    function = ""
    orgs = {}
    ents = {}
    for line in lines:
        content = line.strip(" \n\t")
        if line.find("@Then") >= 0 or line.find("@Given") >= 0 or line.find("@And") >= 0 or line.find("@When") >= 0 or line.find("@But") >=0:
            keyword = line.split("(", 1)[1].replace('\\"([^\\"]*)\\"', "$param").replace("{string}", "$param") \
                .replace("{int}", "$param").replace('\"{int}\"', "$param").replace('\"{word}\"',"$param").rsplit(")", 1)[0].strip("\"$^")
            current_keyword = keyword
        else:
            if line.find("=") <0 and line.find("class") <0 and  (line.find("public ") >= 0 or line.find("public static void ") >= 0 or line.find("private") >=0):
                function = content.split("(",1)[0].rsplit(" ",1)[1]
                functions[function] = []
                if len(current_keyword) > 0:
                    keywords[current_keyword] = function
            else:
                if len(function) > 0 and not line.find("if ") >=0 and not line.find("else ") >=0 and not line.find("for ") >=0:
                    statement = content.split("(")[0]
                    functions[function].append(statement)
                    if statement.find("fillInNextAvailableUsernameAndPasswordAndLogin") >=0:
                        if len(line.split(",")) == 3:
                            org_id = line.split(",")[2]
                            ent_id = line.split(",")[1]
                            if org_id.find("\"") >= 0:
                                org_id = org_id.split("\"")[1]
                                orgs[function]=org_id
                            else:
                                print(org_id)
                            if ent_id.find("\"") >= 0:
                                ent_id = ent_id.split("\"")[1]
                                ents[function]=ent_id
                        else:
                            print(statement)
    res = {}
    for keyword in keywords:
        if keyword.find("$") < 0 and keyword.find("{") and get_org(keywords[keyword],[]):
           res[keyword] =  get_org(keywords[keyword],[])

    for keyword in res:
        print(keyword + ":" + res[keyword])

    org_s = {}

    feature_list = []
    s_list = []
    scenario_list=[]
    scan_feature(input_dir)
    org_list = []
    for org in org_s:
        s_list.append({"name":org,"scenarios":len(org_s[org])})
        # print(org + ":" + str(len(org_s[org])))

    s_list = sorted(s_list,key=lambda item:item["scenarios"])

    scenario_org = {}

    for org in org_s:
        for s in org_s[org]:
            scenario_org[s] = org

    orgs_file = open("orgs.json","w",encoding="utf-8")

    json.dump(scenario_org,orgs_file,indent=4)

    orgs_file.close()

    # for item in s_list:
    #     print(item["name"] + ":" + str(item["scenarios"]))
    #
    # print(str(len(feature_list)))