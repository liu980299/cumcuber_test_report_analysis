
def getStartTime(line, test_date):
    return test_date + line.split(test_date)[1].split(" ")[0]


def email_char(char):
    if char < 48 or ( char > 57 and char < 65) or ( char > 90 and char < 97 ) or char > 122:
        return False
    return True

def validateEmail(email):
    if email.find("@") > 0:
        items = email.split("@")
        if len(items) == 2:
            items[0]

def getEmails(line,cfg):
    res = []
    new_line = line
    if "selector" in cfg:
        for item in cfg["selector"]:
            if new_line.lower().find(item) > 0:
                    new_line = line.split(item)[cfg["selector"][item]]
    items = new_line.split("@")

    for i in range(len(items) - 1):
        left = items[i]
        right = items[i+1]
        for item in cfg["left"]:
            left = left.rsplit(item,1)[-1]
        for item in cfg["right"]:
            right = right.split(item,1)[0]

        # if left.find("auth_") >= 0:
        #     left=left.rsplit("auth_",1)[1]
        # left = left.rsplit("#",1)[-1].rsplit(":",1)[-1].rsplit("[",1)[-1]
        # right = right.split(" ",1)[0].split("_",1)[0].split("#")[0]
        if right.find(".") < 0:
            continue
        email = left + "@" +right
        try:
            s = 0
            while not email_char(ord(email[s])):
                s += 1
            e = len(email)
            while not email_char(ord(email[e - 1])):
                e -= 1
            email = email[s:e]
            res.append(email)
        except Exception as e:
            print(e)
    return res

def matchLine(line, cfg):
    if "include" in cfg:
        if "must" in cfg["include"]:
            for item in cfg["include"]["must"]:
                if line.find(item) < 0:
                    return False
        if "option" in cfg["include"]:
            found = False
            for item in cfg["include"]["option"]:
                if line.find(item) >= 0:
                    found = True
                    break
            if not found:
                return False
    if "exclude" in cfg:
        if "must" in cfg["exclude"]:
            for item in cfg["exclude"]["must"]:
                if line.find(item) >= 0:
                    return False

        if "option" in cfg["exclude"]:
            for item in cfg["exclude"]["option"]:
                found = False
                if line.find(item) < 0:
                    found = True
                    break
            if not found:
                return False

    return True

def processEmail(email):
    s = 0
    while not email_char(ord(email[s])):
        s += 1
    e = len(email)
    while not email_char(ord(email[e - 1])):
        e -= 1
    email = email[s:e]
    return email

def extractLine(line, line_info, name, extract_cfg,global_cfg):
    if "pattern" in extract_cfg:
        pattern_cfg = extract_cfg["pattern"]
        save_global = False
        if type(pattern_cfg) == str:
            if "$extract" in line_info and pattern_cfg in line_info["$extract"]:
                items = line_info["$extract"][pattern_cfg]
                item_res = []
                for item in items:
                    item_res.append(extract_cfg["value"].replace("<left>",item["left"]).replace("<right>",item["right"]))
                if "index" in extract_cfg:
                    line_info[name] = item_res[extract_cfg["index"]]
                else:
                    line_info[name] = item_res
                return
            pattern_cfg = global_cfg[pattern_cfg]
            save_global = True


        res = []
        new_line = line
        if "selector" in pattern_cfg:
            found = False
            for item in pattern_cfg["selector"]:
                found = False
                if new_line.find(item) > 0:
                    if type(pattern_cfg["selector"][item]) == int:
                        new_line = line.split(item)[pattern_cfg["selector"][item]]
                        found = True
                    else:
                        pos = int(pattern_cfg["selector"][item].strip("+-"))
                        if pattern_cfg["selector"][item].find("+") >=0:
                            new_line = item.join(line.split(item)[pos:])
                            found = True
                        else:
                            new_line = item.join(line.split(item)[:pos])
                            found = True
                    break
            if not found:
                return []
        splitter = pattern_cfg["splitter"].replace("\\n","\n")
        if new_line.find(splitter) >= 0:
            items = new_line.split(splitter)
            for i in range(len(items) - 1):
                item_data = {}
                item_data["left"] = items[i]
                item_data["right"] = items[i+1]
                if "left" in pattern_cfg:
                    for item in pattern_cfg["left"]:
                        if type(item) == str:
                            item = item.replace("\\n","\n")
                            item_data["left"]  = item_data["left"].rsplit(item,1)[-1]
                        elif type(item) == dict:
                            for key in item:
                                item_data["left"] =  item_data["left"].rsplit(key,item[key])[-1]
                if "right" in pattern_cfg:
                    for item in pattern_cfg["right"]:
                        if type(item) == str:
                            item = item.replace("\\n", "\n")
                            item_data["right"]  = item_data["right"].split(item,1)[0]
                        elif type(item) == dict:
                            for key in item:
                                item_data["right"] =  item_data["right"].rsplit(key,item[key])[0]

                if "processor" in pattern_cfg:
                    process_cfg = pattern_cfg["processor"]
                    for data_key in ["left","right"]:
                        if data_key in process_cfg:
                            item_data[data_key] = item_data[data_key].strip(process_cfg[data_key].replace("\\n","\n"))

                invalid = False
                if "validator" in pattern_cfg:
                    for selector in ["right","left"]:
                        if selector in pattern_cfg["validator"] and not matchLine(item_data[selector],pattern_cfg["validator"][selector]):
                            invalid = True
                            break
                    if invalid:
                        continue

                value = extract_cfg["value"].replace("<left>", item_data["left"]).replace("<right>", item_data["right"])
                if save_global:
                    if "$extract" not in line_info:
                        line_info["$extract"] = {}
                        line_info["$extract"][extract_cfg["pattern"]]=[]
                    line_info["$extract"][extract_cfg["pattern"]].append(item_data)
                res.append(value)
        else:
            return []

        if len(res) > 0:
            line_info[name] = res
            if "index" in extract_cfg :
                line_info[name] = line_info[name][extract_cfg["index"]]
            elif "type" not in extract_cfg or not extract_cfg["type"] == "list":
                line_info[name] = line_info[name][0]
        return res
    elif "value" in extract_cfg:
        line_info[name] = extract_cfg["value"]

