import jenkins
import argparse,json,re
import requests
import datetime
import os

parser = argparse.ArgumentParser()
parser.add_argument("--jenkins",help="jenkins args",required=True)
parser.add_argument("--data_url",help="analysis data url",required=True)
parser.add_argument("--input_dir",help="input feature dir",required=True)
parser.add_argument("--output_dir",help="output feature dir",required=True)
args = parser.parse_args()


def scan_feature(folder):
    for filename in os.listdir(folder):
        if filename not in [".", ".."]:
            file_path = folder + "/" + filename
            if os.path.isfile(file_path) and filename.find(".feature") > 0:
                feature = {"duration": 0, "scenarios": []}
                current_scenario = ""
                same_container = ""
                lines = open(file_path,"r",encoding="utf-8").readlines()
                all_scenarios = False
                if lines[0].find("@container") >0:
                    all_scenarios = True
                for line in lines:
                    content = line.strip(" \n\t")
                    if content.find("#") == 0 and content.find("same container") > 0:
                        same_container = content.strip("# ")
                    if content.find("@container") >= 0:
                        current_scenario = ""
                    if (len(current_scenario) == 0 or all_scenarios) and (content.find("Scenario:") == 0 or content.find("Scenario Outline:") == 0):
                        current_scenario = content.split(":",1)[1].strip(" ")
                        if current_scenario in scenarios:
                            feature["scenarios"].append(scenarios[current_scenario])
                            feature["duration"] += scenarios[current_scenario]["duration"]
                            if len(same_container)  > 0 :
                                if same_container not in dependences:
                                    dependences[same_container] = {}
                                    dependences[same_container]["scenarios"] = []
                                    dependences[same_container]["features"] = []
                                scenarios[current_scenario]["dependency"] = same_container
                                if "dependency" not in feature:
                                    feature["dependency"] = []
                                if same_container not in feature["dependency"]:
                                    feature["dependency"].append(same_container)
                                dependences[same_container]["scenarios"].append(scenarios[current_scenario])
                                if filename not in dependences[same_container]["features"]:
                                    dependences[same_container]["features"].append(filename)
                        else:
                            print("*** Not found Scenario : " + current_scenario)
                        same_container = ""
                    m = re.search("\"([^\'\"]+@threatmetrix\.com)", content)
                    if not content.startswith(("#")) and content.find("login") >= 0 and m and current_scenario in scenarios:
                        if "test_users" not in scenarios[current_scenario]:
                            scenarios[current_scenario]["test_users"] = []
                        test_user = m.group(1)
                        if test_user not in scenarios[current_scenario]["test_users"]:
                            scenarios[current_scenario]["test_users"].append(test_user)
                if all_scenarios:
                    feature["one_container"] = True
                if len(feature["scenarios"]) > 0:
                    features[filename] = feature
            elif os.path.isdir(file_path):
                scan_feature(file_path)


def get_feature(folder,filepath = None):
    for filename in os.listdir(folder):
        if filename not in [".", ".."]:
            file_path = folder + "/" + filename
            if os.path.isfile(file_path) and filename.find(".feature") > 0:
                current_container = ""
                current_scenario = ""
                container_no = 0
                lines = open(file_path,"r",encoding="utf-8").readlines()
                line_no = 0
                container_line = line_no
                change = False
                set_container = False
                update_lines=[]
                if lines[0].find("@container") >= 0:
                    set_container = True
                    current_container = "@container" + lines[0].split("@container")[1].split(" ")[0]
                    container_no = int(current_container[10:])
                    print(filename + "****" + lines[0].strip(" \n\t"))
                    lines[0] = " ".join([item for item in lines[0].strip("\n").split(" ") if item.find("@container") < 0]) + "\n"
                    change = True
                for line in lines:
                    content = line.strip(" \n\t")
                    if content.find("@container") >= 0:
                        current_container = "@container" + content.split("@container")[1].split(" ")[0]
                        current_scenario = ""
                        container_line = line_no
                    if len(current_scenario) == 0 and (content.find("Scenario:") == 0 or content.find("Scenario Outline:")==0):
                        if content.find("Scenario Outline:") == 0:
                            print(content)
                        current_scenario = content.split(":",1)[1].strip(" ")
                        set_scenario = True
                    if not current_scenario == "" and current_scenario in res and not current_container == "@" + res[current_scenario] and set_scenario:
                        if not set_container:
                            lines[container_line] = lines[container_line].replace(current_container,"@" + res[current_scenario])
                            change = True
                            print(filename + " : " + current_scenario + " : " + res[current_scenario] + ":" + str(scenarios[current_scenario]["duration"]))
                            current_scenario = ""
                        else:
                            update_lines.append("  @" + res[current_scenario] + "\n")
                        set_scenario = False
                    line_no += 1
                    update_lines.append(line)
                if change:
                    path_name = output_dir
                    if filepath:
                        path_name += "/" + filepath
                        if not os.path.exists(path_name):
                            os.makedirs(path_name)
                    new_file = open(path_name+ "/" + filename, "w", encoding="utf-8")
                    if not set_container:
                        new_file.writelines(lines)
                    else:
                        new_file.writelines(update_lines)
                    new_file.close()
            elif os.path.isdir(file_path):
                if filepath:
                    filename = filepath + "/" + filename
                get_feature(file_path, filepath=filename)

def merge(merges):
    new_merges = []
    skips = []
    checked = False
    for i in range(len(merges)):
        if len(skips) == 0:
            for j in range(i + 1,len(merges)):
                for item in merges[i]:
                    if item in merges[j]:
                        skips.append(j)
                        checked=True
        if checked:
            new_merges.append(merges[i] + list(set(merges[j])-set(merges[i])))
            checked = False
        elif i not in skips:
            new_merges.append(merges[i])
    if len(new_merges) ==len(merges):
        return merges
    else:
        return merge(new_merges)

if __name__ == "__main__":
    server_url, job_name, username, password = args.jenkins.split("|")
    data_url = args.data_url
    input_dir = args.input_dir
    output_dir = args.output_dir
    features = {}
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    server = jenkins.Jenkins(server_url, username, password)
    job = server.get_job_info(job_name)
    analysis_json_url = job["lastSuccessfulBuild"]["url"] + data_url
    response = server.jenkins_request(requests.Request('GET', analysis_json_url))
    data = json.loads(response.text)
    containers = []
    total = 0
    for key in data:
        if key.find("qa1") > 0:
            data = data[key]
            break
    scenarios = {}
    dependences = {}
    for container in data["timeline"]:
        # if int(container[9:]) > 80:
        data["timeline"][container]["name"] = container
        container_data = data["timeline"][container]
        start_time = datetime.datetime.strptime(container_data["start_time"],"%Y-%m-%d %H:%M:%S")
        end_time = datetime.datetime.strptime(container_data["end_time"],"%Y-%m-%d %H:%M:%S")
        duration = (end_time - start_time).total_seconds()/60
        container_data["duration"] = duration
        total += duration
        containers.append(container_data)
        for scenario in container_data["scenarios"]:
            start_time = datetime.datetime.strptime(scenario["start_time"], "%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.strptime(scenario["end_time"], "%Y-%m-%d %H:%M:%S")
            duration = (end_time - start_time).total_seconds() / 60
            scenario["duration"] = duration
            if scenario["name"] not in scenarios:
                scenarios[scenario["name"]] = {}
                scenarios[scenario["name"]]["num"] = 1
                scenarios[scenario["name"]]["name"] = scenario["name"]
                scenarios[scenario["name"]]["duration"] = duration
            else:
                scenarios[scenario["name"]]["duration"] += duration
                scenarios[scenario["name"]]["num"] += 1


    scan_feature(input_dir)
    all_dependent_features = []
    feature_groups=[]
    for dependency in dependences:
        if len(dependences[dependency]["features"]) > 1:
            feature_groups.append(dependences[dependency]["features"])
    feature_groups = merge(feature_groups)
    group_features = {}
    for group in feature_groups:
        group_features[",".join(group)]={"features":[],"duration":0}
        for feature_file in group:
            if feature_file not in all_dependent_features:
                all_dependent_features.append(feature_file)
    jobs = []
    job_containers = []
    for i in range(5):
        jobs.append({"name":"job"+str(i),"duration":0,"features":[],"start":i*40 + 1,"dependencies":{}})



    feature_list = []
    for feature in features:
        feature_data = features[feature]
        feature_data["name"] = feature
        if feature.lower().find("case") >= 0:
            jobs[0]["duration"] += feature_data["duration"]
            jobs[0]["features"].append(feature_data)
        elif feature in all_dependent_features:
            for group in group_features:
                if group.find(feature) >= 0:
                    group_features[group]["features"].append(feature_data)
                    group_features[group]["duration"] += feature_data["duration"]
                    break
        else:
            feature_list.append(feature_data)
    jobs = sorted(jobs, key=lambda item: item["duration"])
    dependent_features = []
    for group in group_features:
        dependent_features.append(group_features[group])
    dependent_features = sorted(dependent_features,key= lambda item: item["duration"], reverse=True)
    for dependency in dependent_features:
        jobs[0]["duration"] += dependency["duration"]
        jobs[0]["features"].extend(dependency["features"])
        jobs = sorted(jobs, key=lambda item: item["duration"])

    jobs = sorted(jobs, key=lambda item: item["duration"])
    feature_list = sorted(feature_list,key = lambda item:item["duration"], reverse= True)
    for feature in feature_list:
        jobs[0]["duration"] += feature["duration"]
        jobs[0]["features"].append(feature)
        jobs = sorted(jobs, key=lambda item: item["duration"])


    for job in jobs:
        print(job["name"] + ":" + str(job["duration"]))
        job["scenarios"] = []
        for feature in job["features"]:
            if "one_container" not in feature:
                for scenario in feature["scenarios"]:
                    if "dependency" not in scenario:
                        job["scenarios"].append(scenario)
                    else:
                        if scenario["dependency"] not in job["dependencies"]:
                            job["dependencies"][scenario["dependency"]] = dependences[scenario["dependency"]]
                            dependency = job["dependencies"][scenario["dependency"]]
                            dependency["users"] = scenario["dependency"]
                            dependency["duration"] = 0
                            for scenario_data in dependency["scenarios"]:
                                dependency["duration"] += scenario_data["duration"]

    res = {}

    for job in jobs:
        scenario_list = []
        groups = {}
        merges = []
        merge_list= []
        for scenario_data in job["scenarios"]:
            scenario = scenario_data["name"]
            if "test_users" not in scenarios[scenario]:
                scenario_list.append(scenarios[scenario])
            else:
                for test_user in scenarios[scenario]["test_users"]:
                    if test_user not in groups:
                        groups[test_user] = {}
                        groups[test_user]["scenarios"] = {}
                        groups[test_user]["scenario_list"] =[]
                    groups[test_user]["scenarios"][scenario] = scenarios[scenario]
                    groups[test_user]["scenario_list"].append(scenario)
                if len(scenarios[scenario]["test_users"]) > 1:
                    existing = False
                    for item in merges:
                        for test_user in scenarios[scenario]["test_users"]:
                            if test_user in item:
                                for user in scenarios[scenario]["test_users"]:
                                    if user not in item:
                                        item.append(user)
                                        if user not in merge_list:
                                            merge_list.append(user)
                                        else:
                                            print("wrong user : " + user)
                                        existing = True
                                break
                        if existing:
                            break
                    if not existing:
                        merges.append(scenarios[scenario]["test_users"])
                        for user in scenarios[scenario]["test_users"]:
                            if user not in merge_list:
                                merge_list.append(user)

        merges = merge(merges)
        print(json.dumps(groups,indent=4))
        for test_user in groups:
            if test_user not in merge_list:
                group={}
                group["duration"] = 0
                group["scenarios"] = []
                group["scenario_list"] = []
                for scenario in groups[test_user]["scenario_list"]:
                    if scenario not in group["scenario_list"]:
                        group["scenarios"].append(groups[test_user]["scenarios"][scenario])
                        group["duration"] += groups[test_user]["scenarios"][scenario]["duration"]
                        group["scenario_list"].append(scenario)
                        group["users"] = [test_user]
                scenario_list.append(group)

        for item in merges:
            group = {}
            group["duration"] = 0
            group["scenarios"] = []
            group["scenario_list"] = []
            for user in item:
                for scenario in groups[user]["scenario_list"]:
                    if scenario not in group["scenario_list"]:
                        group["scenarios"].append(groups[user]["scenarios"][scenario])
                        group["duration"] += groups[user]["scenarios"][scenario]["duration"]
                        group["scenario_list"].append(scenario)
            group["users"] = item
            scenario_list.append(group)

        for feature in job["features"]:
            if "one_container" in feature:
                scenario_list.append(feature)

        if "dependencies" in job:
            for dependency in job["dependencies"]:
                if len(job["dependencies"][dependency]) > 0:
                    scenario_list.append(job["dependencies"][dependency])
                else:
                    print(dependency)

        scenario_list = sorted(scenario_list, key=lambda item: item["duration"], reverse=True)




        container_list = []
        for i in range(40):
            item = {"name":"container" + str(job["start"] + i), "duration": 0,"scenarios":[]}
            container_list.append(item)


        for scenario in scenario_list:
            container_list[0]["scenarios"].append(scenario)
            container_list[0]["duration"] -= scenario["duration"]
            if "scenarios" in scenario:
                for scenario_item in scenario["scenarios"]:
                    scenario_item["container"] = container_list[0]["name"]
                    res[scenario_item["name"]] = container_list[0]["name"]
                    if scenario_item["name"] in scenarios:
                        scenarios[scenario_item["name"]]["checked"] = True
            else:
                if scenario["name"] in scenarios:
                    scenarios[scenario["name"]]["checked"] = True
                res[scenario["name"]] = container_list[0]["name"]
            scenario["container"] = container_list[0]["name"]
            container_list = sorted(container_list, key=lambda item: item["duration"], reverse=True)
        job_containers.append(container_list)

    get_feature(input_dir)

    # print(json.dumps(res, indent=4))
    #

    total = 0
    for container_list in job_containers:
        for container in container_list:
            durations = []
            sub_total = 0
            for item in container["scenarios"]:
                sub_total += item["duration"]
                durations.append(item["duration"])
                if item["duration"] > 60:
                    if "scenarios" in item:
                        print("---------------")
                        print(str(item["users"]) + ":" + str(item["duration"]))
                        for scenario in item["scenarios"]:
                            print(scenario["name"] + "  :  " + str(scenario["duration"]))
                        print("################")
                    else:
                        print(item["name"] + "  :   " + str(item["duration"]))

            total += sub_total

    avg = total/len(containers)
    # print(len(containers))
    test_num = 0
    for scenario in scenarios:
        test_num += scenarios[scenario]["num"]
    print("total : " + str(test_num))
    print("avg : " + str(avg))


    for scenario in scenarios:
        if not "checked" in scenarios[scenario]:
            print(scenario)
