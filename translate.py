import argparse
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument("--input",help="cucumber steps java file folder",required=True)
parser.add_argument("--output",help="project folder",required=True)
args = parser.parse_args()

if __name__ == "__main__":
    input_dir = args.input
    output_dir = args.output

    files = os.listdir(input_dir)
    java_files = [file for file in files if file.endswith(".java")]
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    res ={}
    for java_file in java_files:
        py_text = ""
        lines = open(input_dir+"/"+java_file,"r",encoding="utf-8").readlines()
        cls_name = java_file.split(".")[0]
        is_step = False
        for line in lines:
            if line.find("@Then") >= 0 or line.find("@Given") >= 0 or line.find("@And") >= 0 or line.find("@When") >= 0 or line.find("@But") >=0:
                keyword = line.split("(",1)[1].replace('\\"([^\\"]*)\\"',"$param").replace("{string}","$param")\
                    .replace("{int}","$param").replace('\"{int}\"',"$param").rsplit(")",1)[0].strip("\"$^")
                keyword = keyword.replace("$param", "{}").replace("(\\\\d+)","{}").replace("\\\\","").replace("\\\"","")
                res[keyword] = java_file


    print(json.dumps(res,indent=4))




