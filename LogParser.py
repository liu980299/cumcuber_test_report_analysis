import datetime
import os, json
import zipfile

from utils import getEmails,email_char,getStartTime,matchLine,extractLine



class LogParser:
	def __init__(self, log_file, test_date,log_cfg):
		self.log_file = log_file
		self.test_date = test_date
		self.log_cfg = log_cfg
		logFile = open(self.log_file,"r",encoding="utf-8")
		self.name = self.log_file.split(".")[0]
		self.lines = logFile.readlines()
		self.threads = {}
		self.current_error = None
		self.errors = {}
		self.unknown = None
		self.error_list = []
		self.stacks = {}
		self.content_lists={"session":[]}
		self.session_list = self.content_lists["session"]
		self.current_stack = None
		self.current_keys = {}
		self.current_key = None
		self.current_threads={"session":{}}
		self.current_session = self.current_threads["session"]
		self.issue_list = {}
		self.dependency = {}
		self.log_units_history = {}
		self.log_units = {}
		self.sessions={}
		self.apis={}
		self.others = {}
		self.contents = {}
		self.no_thread_erros = []
		self.key = log_cfg["key"]
		self.maps = {}
		self.current_error_index = None
		self.current_stack_index = None
		self.sort_by_thread  = False
		self.machine = None
		self.key_maps = None
		self.refs = {}
		self.unknown_units = {}
		if "contents" in self.log_cfg["thread"] and "id" in self.log_cfg["thread"]["contents"]["session"]:
			self.sort_by_thread = True
			self.threads["session"] = {}
		if "no_key_contents" in self.log_cfg:
			for item in self.log_cfg["no_key_contents"]:
				self.contents[item] = {"index":[]}
		else:
			self.log_cfg["no_key_contents"] = []
		if "maps" in self.log_cfg:
			self.maps[self.key] = {}
			for map in self.log_cfg["maps"]:
				self.maps[map] = {}
				self.maps[self.key][map] = {}
		if "machine" in self.log_cfg:
			self.machine =  self.log_cfg["machine"]

	def setKeysMap(self, keyMaps):
		self.key_maps = {}
		self.refs = {}
		for key_map in self.log_cfg["key_maps"]:
			self.refs[self.log_cfg["key_maps"][key_map]["map"]] = key_map
			items= self.log_cfg["key_maps"][key_map]["path"].split(":")
			target = keyMaps
			for item in items:
				target = target[item]
			self.key_maps[key_map] = target

	def setupThread(self):
		thread_cfg = self.log_cfg["thread"]
		for line_no in range(len(self.lines)):
			line = self.lines[line_no]
			machine = None
			if self.machine:
				for key in self.machine:
					machine = line.split(key,self.machine[key] + 1)[self.machine[key]]
			if len(line.split(thread_cfg["left"])) >= 2 and line.find(self.test_date) > 0:
				thread_no = line.split(thread_cfg["left"])[1].split(thread_cfg["right"])[0]
				thread_res = {}
				if "contents" in thread_cfg:
					thread_contents = thread_cfg["contents"]
					for content in thread_contents:
						if thread_no.find(thread_contents[content]["match"]) >=0:
							content_cfg = thread_contents[content]
							items = thread_no.split(content_cfg["splitter"])
							thread_res["thread"] = items[content_cfg["thread"]]
							thread_res["type"] = content
							if "id" in content_cfg:
								thread_res["id"] = items[content_cfg["id"]]
							break
				else:
					thread_no = thread_no.split(",")[0].split("|")[0].strip()
				log_time = getStartTime(line, self.test_date)
				line_info = {"log_time":log_time,"msg":line,"thread":thread_no}
				if len(thread_res) > 0:
					self.thread_no = thread_res["thread"]
					line_info["$thread"] = thread_res
				else:
					# self.thread_no  = thread_no
					thread_index = machine + "|" + thread_no
					if thread_index not in self.threads:
						self.threads[thread_index] = {"index":[]}
					thread_data = self.threads[thread_index]
					if "sub_index" in self.log_cfg:
						sub_index = log_time[:self.log_cfg["sub_index"]]
						time_index = log_time[self.log_cfg["sub_index"] + 1:]
						if sub_index not in thread_data:
							sub_index_item = {time_index:[line_info]}
							self.injectByTime(thread_data,sub_index_item,log_time=sub_index)
						else:
							if time_index in thread_data[sub_index]:
								thread_data[sub_index][time_index].append(line_info)
							else:
								thread_data[sub_index][time_index] = [line_info]
							# self.insertByTime(self.threads[self.thread_no][sub_index],line_info,field="log_time")

					# self.insertByTime(self.threads[self.thread_no],line_info,field="log_time")

				self.parseLineError(line,thread_no,line_info)
			else:
				self.processError(line)

	def setValues(self, line_info):
		log_unit = self.log_units[self.thread_no]
		if len(line_info) > 0:
			if self.key not in log_unit and self.key in line_info:
				log_unit[self.key] = line_info[self.key]
				# self.register(log_unit)
				# self.setSession(log_unit["type"], log_unit)
				for map in self.maps:
					if not map == self.key and map in log_unit:
						self.setMapValue(map,log_unit)
			elif self.key in log_unit and self.key in line_info and not line_info[self.key] == log_unit[self.key]:
				if ("dependencies" not in log_unit and "dependencies" not in line_info) or \
				   ("dependencies" in log_unit and line_info[self.key] not in log_unit["dependencies"]) or \
				   ("dependencies" in line_info and log_unit[self.key] not in line_info["dependencies"])	:
					return False
			key_names = [key_name for key_name in line_info]
			if "key_maps" in self.log_cfg:
				for key_name in key_names:
					if key_name in self.log_cfg["key_maps"]:
						map_key = self.log_cfg["key_maps"][key_name]["map"]
						refValue = self.getRefValue(map_key,line_info)
						if refValue:
							line_info[map_key] = refValue
							if map_key == self.key:
								if self.key not in log_unit :
									log_unit[self.key] = refValue
								elif not log_unit[self.key] == refValue:
									return False
							else:
								log_unit[map_key] = refValue


			if "$thread" in line_info and "id" in line_info["$thread"]:
				log_unit["id"] = line_info["$thread"]["id"]


			# if "start_time" not in log_unit or line_info["log_time"] < log_unit["start_time"]:
			# 	log_unit["start_time"] = line_info["log_time"]
			for key_name in line_info:
				if not key_name.startswith("$") and not key_name == self.key:
					if key_name not in log_unit:
						log_unit[key_name] = line_info[key_name]
					elif key_name not in self.log_cfg["unique_keys"]:
						if type(log_unit[key_name]) == list:
							if line_info[key_name] not in log_unit[key_name]:
								log_unit[key_name].append(line_info[key_name])
						elif not log_unit[key_name] == line_info[key_name]:
							log_unit[key_name] = [log_unit[key_name],line_info[key_name]]

				if key_name in self.maps and self.key in log_unit and not key_name  == self.key:
					self.setMapValue(key_name,log_unit)

		return True


	def setMapValue(self,key,log_unit):
		if not key == self.key and key in log_unit:
			key_map = self.maps[self.key][key]
			# if type(log_unit[key]) == list:
			# 	print(log_unit)
			if log_unit[key] not in self.maps[key]:
				self.maps[key][log_unit[key]] = log_unit[self.key]
			else:
				if type(self.maps[key][log_unit[key]]) == str:
					self.maps[key][log_unit[key]] = [self.maps[key][log_unit[key]]]
				if log_unit[self.key] not in self.maps[key][log_unit[key]]:
					self.maps[key][log_unit[key]].append(log_unit[self.key])
			if log_unit[self.key] not in key_map:
				key_map[log_unit[self.key]] = log_unit[key]
			else:
				if type(key_map[log_unit[self.key]]) == str:
					key_map[log_unit[self.key]] = [key_map[log_unit[self.key]]]
				if log_unit[key] not in key_map[log_unit[self.key]]:
					key_map[log_unit[self.key]].append(log_unit[key])

	def getThreadType(self, line_res, line_info):
		line = line_res["msg"]
		contents_cfg = self.log_cfg["contents"]
		global_cfg = self.log_cfg["extract"]
		if "$thread" in line_info:
			thread_info = line_info["$thread"]
			if "id" in thread_info:
				if thread_info["id"] not in self.threads[thread_info["type"]]:
					if thread_info["type"] not in self.threads:
						self.threads[thread_info["type"]] = {}
					if "id" in thread_info and thread_info["id"] not in self.threads[thread_info["type"]]:
						self.threads[thread_info["type"]][thread_info["id"]] = thread_info
					return thread_info["type"]
			elif "id" not in thread_info and "distributed" in self.log_cfg["contents"][thread_info["type"]]:
				if "extract" in contents_cfg[thread_info["type"]]:
					for name in contents_cfg[thread_info["type"]]["extract"]:
						extract_cfg = contents_cfg[thread_info["type"]]["extract"][name]
						extractLine(line, line_info, name, extract_cfg, global_cfg)
				return thread_info["type"]
			else:
				match_cfg_list= contents_cfg[thread_info["type"]]
				if self.matchLine(line,match_cfg_list,line_info,self.log_cfg["extract"]):
					return thread_info["type"]
		else:
			for content in contents_cfg:
				content_cfg = contents_cfg[content]
				if "matches" in content_cfg:
					match_cfg_list = content_cfg["matches"]
					for match_cfg in match_cfg_list:
						if matchLine(line, match_cfg):
							if "extract" in match_cfg:
								extract_cfgs = match_cfg["extract"]
								for name in extract_cfgs:
									extract_cfg = extract_cfgs[name]
									extractLine(line,line_info,name, extract_cfg,global_cfg)
							if ("line_no" not in match_cfg or self.thread_no not in self.log_units) and "distributed" not in contents_cfg:
								return content
							elif "line_no" in match_cfg:
								# line_no = len(self.threads[self.thread_no]) - self.log_units[self.thread_no]["start"]
								line_no = len(self.log_units[self.thread_no]["msg"]) + 1
								if not match_cfg["line_no"] == line_no:
									return content
							elif "distributed" in contents_cfg:
								distributed = contents_cfg["distributed"]
								log_unit = self.log_units[self.thread_no]
								if self.key not in log_unit:
									return content
								if distributed == self.key:
									if not line_info[distributed] == log_unit[self.key]:
										return content
								else:
									if line_info[distributed] not in self.maps[distributed] or not line_info[self.key] == self.maps[distributed][line_info[distributed]]:
										return content
						# self.setValues(line_info)
		if self.thread_no in self.log_units:
			log_unit = self.log_units[self.thread_no]
			if "log_file" not in log_unit:
				log_unit["log_file"] = self.name
			if "start_time" not in log_unit:
				log_unit["start_time"] = line_res["log_time"]
			log_type = log_unit["type"]
			if log_type in contents_cfg:
				if "extract" in contents_cfg[log_type]:
					for name in contents_cfg[log_type]["extract"]:
						extract_cfg = contents_cfg[log_type]["extract"][name]
						res = extractLine(line, line_info, name, extract_cfg, global_cfg)
						if res and name == self.key and len(res) > 1:
							line_info["dependencies"] = res
						# self.register()
				if not self.setValues(line_info):
					if len(self.log_cfg["contents"]) == 1:
						return "session"
					return "unknown"
				if "end" in self.log_cfg["contents"][log_type]:
					if self.matchLine(line,self.log_cfg["contents"][log_type]["end"],line_info,self.log_cfg["extract"]):
						self.endThread()
			log_unit["msg"].append(line)
			log_unit["end_time"] = line_res["log_time"]
			if "error" in line_res:
				self.setErrorByLine(log_unit,line_res)

			if self.key in line_info and self.key in log_unit and not line_info[self.key] == log_unit[self.key]  \
					and ("dependencies" not in log_unit or line_info[self.key] not in log_unit["dependencies"]):
				# self.endThread()
				# print(line)
				if len(self.log_cfg["contents"]) == 1:
					return "session"

		return ""

	def setErrorByLine(self,log_unit, line_res):
		if "error" not in log_unit:
			error = {"items": {}}
			log_unit["error"] = error
			self.error_list.append(error)
			error["id"] = len(self.error_list)
		error = log_unit["error"]
		if line_res["error"]["level"] in ["ERROR", "FATAL"]:
			log_unit["error"]["level"] = line_res["error"]["level"]
			error["msg"] = line_res["msg"]
		if "stacks" in line_res["error"]:
			if "stacks" not in error:
				error["stacks"] = {}
			for exception in line_res["error"]["stacks"]:
				log_unit["error"]["stacks"][exception] = line_res["error"]["stacks"][exception]
			self.getStacksName(log_unit["error"])
			for key in line_res["error"]:
				log_unit["error"][key] = line_res["error"][key]
			# having stacks level would be promoted to be ERROR
			if not log_unit["error"]["level"] == "FATAL":
				log_unit["error"]["level"] = "ERROR"
		log_unit["error"]["items"][len(log_unit["msg"])] = line_res["error"]
		if "type" in log_unit:
			log_unit["error"]["type"] = log_unit["type"]

	def endThread(self):
		if self.thread_no in self.log_units:
			log_type = self.log_units[self.thread_no]["type"]
			if log_type in self.log_cfg["contents"]:
				content_cfg = self.log_cfg["contents"][log_type]
				if "sub_type" not in content_cfg and "distributed" not in content_cfg:
					self.setContent()
			else:
				if self.unknown and not self.unknown["thread"] == self.thread_no:
					self.setUnknown(self.unknown)
					self.injectContent("unknown",self.unknown)
				self.unknown = self.log_units[self.thread_no]
			self.log_units.pop(self.thread_no)

	def startThread(self, thread_index):
		machine,threadNo = thread_index.split("|",1)
		self.log_units[threadNo] ={"type":"unknown","msg":[],"thread":threadNo}

	def insertOthers(self,content, log_unit):
		self.setUnknown(log_unit)
		if content in self.log_cfg["contents"] and "distributed" in self.log_cfg["contents"][content]:
			if content not in self.others:
				self.others[content] = []
			self.others[content].append(log_unit)
			return

		if self.key not in log_unit and "name" in log_unit:
			if "no_key" not in self.others:
				self.others["no_key"] = {}
			if log_unit["name"] not in self.others["no_key"]:
				self.others["no_key"][log_unit["name"]] = []
			self.others["no_key"][log_unit["name"]].append(log_unit)
		if content not in self.others:
			self.others[content] = {}
		if self.key not in log_unit and content == "error":
			name = "others"
			if "name" in log_unit:
				name = log_unit["name"]
			if name not in self.others["error"]:
				self.others["error"][name] = {}
			if log_unit["thread"] not in self.others["error"][name]:
				self.others["error"][name][log_unit["thread"]] = {}
			self.others["error"][name][log_unit["thread"]][log_unit["start_time"]] = log_unit

		else:
			if log_unit["type"] not in self.others[content]:
				self.others[content][log_unit["type"]] = {}
			others = self.others[content][log_unit["type"]]
			if log_unit["thread"] not in others:
				others[log_unit["thread"]] = {"index":[]}
			self.injectByTime(self.others[content][log_unit["type"]][log_unit["thread"]], log_unit,is_others=True)

	def insertByTime(self,item_list,item,field=None):
		index = len(item_list)
		length = index

		if not field:
			field = "start_time"
		for i in range(1, length + 1 ):
			if item[field] > item_list[length - i][field]:
				index = length - i + 1
				break
			index = length - i
		if index == length:
			item_list.append(item)
		else:
			item_list.insert(index,item)
		return index


	def setCurrentLogUnit(self,log_unit):
		if log_unit["thread"] not in self.log_units_history:
			self.log_units_history[log_unit["thread"]] = []
		history = self.log_units_history[log_unit["thread"]]
		self.insertByTime(history,log_unit)
		self.log_units[self.thread_no] = log_unit

	def proccessUnit(self,line_res, thread_type, line_info):
		line = line_res["msg"]
		log_unit = self.log_units[self.thread_no]
		if self.key in log_unit:
			pre_key = log_unit[self.key]
		log_unit = {"thread": self.thread_no, "start_time": line_res["log_time"], "msg": [line],"type":thread_type}


	def injectContent(self,content,log_unit,log_time=None):
		if not log_time:
			log_time = log_unit["start_time"]


		if content in self.log_cfg["no_key_contents"]:
			content_key = self.log_cfg["no_key_contents"][content]
			if content_key not in log_unit:
				print("*** not found content_key in log unit " + str(log_unit))
			unit_content_key = log_unit[content_key]

			if content not in self.contents:
				self.contents[content] = {}
			if  unit_content_key not in self.contents[content]:
				self.contents[content][unit_content_key] =  {"index":[]}
			self.injectByTime(self.contents[content][unit_content_key],log_unit,log_time)
		else:
			if content not in self.contents:
				self.contents[content] = {"index":[]}
			if content in self.log_cfg["contents"] and "sub_index" in self.log_cfg["contents"][content]:
				sub_index = log_time[:self.log_cfg["contents"][content]["sub_index"]]
				if sub_index in self.contents[content]:
					self.injectByTime(self.contents[content][sub_index],log_unit,log_time)
				else:
					sub_content = {"index":[log_time],log_time:[log_unit]}
					self.injectByTime(self.contents[content],sub_content,sub_index)
			else:
				self.injectByTime(self.contents[content],log_unit,log_time)

	def startLogUnit(self,line_res,line,thread_type,pre_key,line_info):
		log_unit = {"thread": self.thread_no, "start_time": line_res["log_time"], "msg": [line]}
		log_unit["type"] = thread_type
		if len(pre_key) > 0:
			log_unit["pre_key"] = pre_key
		log_unit["start_time"] = line_res["log_time"]

		self.log_units[self.thread_no] = log_unit
		self.setValues(line_info)
		if "error" in line_res:
			self.setErrorByLine(log_unit, line_res)

	def setSubType(self, line,line_res,line_info,thread_type):
		log_unit = {"thread": self.thread_no, "start_time": line_res["log_time"], "msg": [line]}
		if "start_time" not in log_unit:
			log_unit["start_time"] = line_res["log_time"]
		log_unit["sub_type"] = thread_type
		log_unit["type"] = self.log_cfg["contents"][thread_type]["type"]
		if "name" in self.log_cfg["contents"][thread_type]:
			log_unit["name"] = self.log_cfg["contents"][thread_type]["name"]
		log_unit["msg"].append(line)
		self.log_units[self.thread_no] = log_unit
		self.setValues(line_info)
		self.injectContent(log_unit["sub_type"], log_unit, line_res["log_time"])

	def processThread(self, line_res, thread_type, line_info):
		# log_start = len(self.threads[self.thread_no]) - 1
		line = line_res["msg"]
		# if "start" in self.log_cfg["contents"][thread_type]:
		# 	log_start = len(self.threads[self.thread_no]) - self.log_cfg["contents"][thread_type]["start"]
		# log_end = log_start - 1

		pre_key = ""
		if self.thread_no in self.log_units and self.key in self.log_units[self.thread_no]:
			pre_key = self.log_units[self.thread_no][self.key]
		if thread_type in self.log_cfg["contents"]:
			content_cfg = self.log_cfg["contents"][thread_type]
		else:
			content_cfg = {}
		if self.thread_no in self.log_units and "sub_type" not in content_cfg and "distributed" not in content_cfg:
			self.setContent()
				# self.injectByTime(self.contents[log_unit["type"]],log_unit)
			# self.endThread()
		elif "sub_type" in content_cfg:
			if self.thread_no in self.log_units:
				log_unit = self.log_units[self.thread_no]
				if "name" in content_cfg:
					if "name" in log_unit and log_unit["name"] == content_cfg["name"]:
						self.setSubType(line,line_res,line_info,thread_type)
					else:
						self.setContent()
						self.startLogUnit(line_res,line,content_cfg["type"],pre_key,line_info)
		elif "distributed" in content_cfg:
			if thread_type not in self.contents:
				self.contents[thread_type] = []
			for key in line_res:
				line_info[key] =line_res[key]
			self.contents[thread_type].append(line_info)


		if "sub_type" not in content_cfg and "distributed" not in content_cfg:
			if self.thread_no in self.log_units and self.key in self.log_units[self.thread_no]:
				pre_key = self.log_units[self.thread_no][self.key]
			if self.thread_no in self.log_units and "type" not in self.log_units[self.thread_no]:
				self.log_units["type"] = "unknown"
			self.startLogUnit(line_res,line,thread_type,pre_key,line_info)

	def mergeUnknown(self, log_unit):
		for key in self.unknown:
			if key not in log_unit:
				log_unit[key] = self.unknown[key]
		log_unit["msg"] = self.unknown["msg"] + log_unit["msg"]
		log_unit["start_time"] = self.unknown["start_time"]
		log_unit["merge_msg_len"] = len(self.unknown["msg"])
		self.unknown = None

	def setContent(self):
		log_unit = self.log_units[self.thread_no]
		if len(log_unit["msg"]) > 1:
			if self.key in log_unit and \
				self.unknown:
				if self.key in self.unknown and not self.unknown[self.key] == log_unit[self.key]:
					self.injectContent("unknown", self.unknown)
					self.unknown = None
				else:
					self.mergeUnknown(log_unit)

			if not log_unit["type"] in ["session","unknown"]:
				self.injectContent(log_unit["type"], log_unit)
			elif log_unit["type"] == "session":
				if self.key in log_unit:
					self.setSession(log_unit["type"], log_unit)
				else:
					self.insertOthers("session", log_unit)
			else:
				self.unknown = log_unit
		if "error" in log_unit:
			error = log_unit["error"]
			if "name" in log_unit:
				error["api"] = log_unit["name"]
			if "name" not in error:
				line_nos = [int(line_no) for line_no in error["items"]]
				line_nos.sort(reverse=True)
				for line_no in line_nos:
					item = error["items"][line_no]
					if item["level"] in ["ERROR","FATAL"]:
						for key in item:
							error[key] = item[key]
						break
			if self.key in log_unit:
				error[self.key] = log_unit[self.key]


	def injectByTime(self,group,log_unit,log_time=None, is_others=False):
		if not log_time:
			log_time = log_unit["start_time"]
		if log_time not in group:
			if "start_time" not in log_unit or log_unit["type"] == "session":
				group[log_time] = log_unit
			else:
				group[log_time] = [log_unit]
			length = len(group["index"])
			if length == 0:
				group["index"].append(log_time)
			else:
				for index in range(length-1, -1, -1):
					if group["index"][index] < log_time:
						group["index"].insert(index + 1, log_time)
						break
					if index == 0:
						group["index"].insert(0, log_time)
		else:
			if not is_others:
				if not log_unit["type"] == "session":
					group[log_time].append(log_unit)
				else:
					log_unit["duplicated"] = group[log_time]["id"]
					print("*** duplicated sesssions :" + str(log_unit))
					self.insertOthers("duplicated",log_unit)
			else:
				if not type(group[log_time]) == list:
					group[log_time] = [group[log_time]]
				group[log_time].append(log_unit)



	def setSession(self,thread_type,log_unit):
		if thread_type == "session" and self.key in log_unit:
			key = log_unit[self.key]
			# if key in self.current_session and "fake" in self.current_session[key] and self.current_session[key][
			# 	"start_time"] > log_unit["start_time"]:
			# 	self.current_session[key].pop("fake")
			# 	for item in log_unit:
			# 		self.current_session[key][item] = log_unit[item]
			# 	self.log_units[self.thread_no] = self.current_session[key]
			# else:
				# log_unit["workers"] = []
				# log_unit["jobs"] = []
			self.session_list.append(log_unit)
			log_unit["id"] = len(self.session_list)
			self.current_session[log_unit[self.key]] = log_unit


			if "error" in log_unit:
				log_unit["error"]["session"] = log_unit["id"]
				if self.key in log_unit:
					log_unit["error"][self.key] = log_unit[self.key]
				if "ref_key" in self.log_cfg and self.log_cfg["ref_key"] in log_unit:
					log_unit["error"][self.log_cfg["ref_key"]] = log_unit[self.log_cfg["ref_key"]]
			# self.current_keys[self.thread_no] = log_unit[self.key]
			if log_unit[self.key] not in self.sessions:
				self.sessions[log_unit[self.key]] = {"index":[]}
			self.injectByTime(self.sessions[log_unit[self.key]],log_unit)

	def setLogUnitError(self,log_unit):
		if "error" in log_unit:
			error = log_unit["error"]

			error[self.key] = log_unit[self.key]
			if "unique_keys" in self.log_cfg:
				for unique_key in self.log_cfg["unique_keys"]:
					if unique_key in log_unit and not unique_key == "name":
						error[unique_key] = log_unit[unique_key]

	def setSessionError(self,log_unit,parent):
		if "error" in log_unit and "level" in log_unit["error"]:
			error = log_unit["error"]
			self.setLogUnitError(log_unit)
			error[log_unit["type"]] = log_unit["id"]
			error[parent["type"]] = parent["id"]
			if "errors" not in parent:
				parent["errors"] = {}
				parent["errors"][self.name] = {}
			parent["errors"][self.name][error["id"]] = error
			if "level" not in parent:
				parent["level"] = error["level"]
			elif not parent["level"] == "ERROR":
				parent["level"] = error["level"]


	def getSession(self, key,start_time):
		# start_time = log_unit["start_time"]
		if key in self.sessions:
			sessions = self.sessions[key]
			# if "index" not in sessions:
			# 	print(sessions)
			session_times = sessions["index"]
			for i in range(len(session_times) - 1, -1, -1):
				if session_times[i] <= start_time:
					return sessions[session_times[i]]

	def getContent(self, content,log_unit):
		start_time = log_unit["start_time"]
		group_times = None
		group = self.contents[content]
		if content in self.log_cfg["no_key_contents"]:
			map_key = self.log_cfg["no_key_contents"][content]
			if map_key in log_unit and log_unit[map_key] in self.contents[content]:
				group_times = self.contents[content][log_unit[map_key]]["index"]
				group = self.contents[content][log_unit[map_key]]
			elif self.key in log_unit and log_unit[self.key] in self.maps[self.key][map_key]:
				map_key_values = self.maps[self.key][map_key][log_unit[self.key]]
				value_dict = {}
				if type(map_key_values) == str:
					target_time = self.getCloseTime(self.contents[content][map_key_values]["index"],start_time)
					value_dict[target_time] = map_key_values
				else:
					target_time = None
					for map_key_value in map_key_values:
						if map_key_value in self.contents[content]:
							group_time = self.getCloseTime(self.contents[content][map_key_value]["index"],start_time)
							if group_time:
								value_dict[group_time] = map_key_value
								if not target_time or target_time < group_time:
									target_time = group_time
				if target_time:
					target = self.contents[content][value_dict[target_time]][target_time]
					if type(target) == list:
						if len(target) == 1:
							return target[0]
						else:
							no_key_items = []
							for item in target:
								if self.refs[self.key] in item:
									refValue = self.getRefValue(self.key,item)
									if refValue:
										item[self.key] = refValue
									if self.key in item:
										if self.key in log_unit and log_unit[self.key] == item[self.key]:
											return item
									else:
										no_key_items.append(item)
							if len(no_key_items) == 1:
								return no_key_items[0]
							else:
								# print(target)
								return
					else:
						return target
				# else:
				# 	print(log_unit)
		else:
			group_times = self.contents[content]["index"]
		if group_times == None:
			print("*** not finding group times for content : " + content)
		else:
			group_time = self.getCloseTime(group_times,start_time)
			if group_time:
				if type(group[group_time]) == list:
					if not len(group[group_time]) == 1:
						print("***unexpected multiple group times :" + str(group[group_time]))
					else:
						return group[group_time][0]
				else:
					return group[group_time]
			# else:
			# 	print(start_time)

	def getCloseTime(self,group_times,start_time):
		if len(group_times) > 0:
			for i in range(len(group_times) - 1, -1, -1):
				if group_times[i] <= start_time:
					return group_times[i]

	def getRefValue(self,key_name,log_unit):
		if key_name in self.refs and key_name not in log_unit:
			map_key = self.refs[key_name]
			if  map_key in self.key_maps and map_key in log_unit:
				unit_map_key = log_unit[map_key].strip()
				if unit_map_key in self.key_maps[map_key]:
					if type(self.key_maps[map_key][unit_map_key]) == list:
						return self.key_maps[map_key][unit_map_key][0]
					else:
						return self.key_maps[map_key][unit_map_key]
	def setUnknown(self,log_unit):
		if log_unit["thread"] not in self.unknown_units:
			self.unknown_units[log_unit["thread"]] = []
		self.unknown_units[log_unit["thread"]].append(log_unit)
		log_unit["id"] = len(self.unknown_units[log_unit["thread"]])
		if "error" in log_unit:
			log_unit["error"]["unknown"] = log_unit["id"]

	def register(self, log_unit, parent = None,final=False):
		# log_unit = self.log_units[self.thread_no]
		thread_type = log_unit["type"]
		thread_cfg = self.log_cfg["contents"][thread_type]

		if "register" in thread_cfg and "msg" in log_unit and len(log_unit["msg"]) > 1:
			for register in thread_cfg["register"]:
				if "register" not in log_unit or register not in log_unit["register"]:
					register_cfg = thread_cfg["register"][register]
					content = register
					name = register_cfg["name"]
					if content not in self.log_cfg["no_key_contents"]:
						# if log_unit[self.key] not in self.current_threads[content]:
						# 	fake_content = {self.key: log_unit[self.key], "type": content,
						# 					"start_time": log_unit["start_time"], "fake": True}
						# 	self.current_threads[content][log_unit[self.key]] = fake_content
						# 	self.content_lists[content].append(fake_content)
						# 	fake_content["id"] = len(self.content_lists[content])
						# 	self.current_threads[content][log_unit[self.key]] = fake_content
						# 	self.setSession("session",fake_content)
						if self.key not in log_unit:
							# if not final:
							# 	self.insertOthers(content,log_unit)
							# else:
							self.insertOthers("error", log_unit)
							self.setUnknown(log_unit)
							continue
						# self.current_keys[self.thread_no] = log_unit[self.key]
						if content == "session":
							parent = self.getSession(log_unit[self.key],log_unit["start_time"])
							if not parent:
								fake_content = {self.key: log_unit[self.key], "type": content,
												"start_time": log_unit["start_time"], "fake": True}
								self.setSession("session",fake_content)
								parent = fake_content
						else:
							parent = self.getContent(content,log_unit)
						if not parent:
							self.insertOthers(content,log_unit)
						else:
							if "id" in parent:
								log_unit[content] = parent["id"]
							if "fake" in parent:
								if log_unit["start_time"] < parent["start_time"]:
									parent["start_time"] = log_unit["start_time"]

							if name not in parent:
								parent[name] = []
							self.insertByTime(parent[name],log_unit)
							if content == "session":
								log_unit["id"] = len(parent[name])
							self.setSessionError(log_unit,parent)

					else:
						map_key = self.log_cfg["no_key_contents"][content]
						# if map_key not in log_unit:
						# 	refValue = self.getRefValue(map_key, log_unit)
						# 	if refValue:
						# 		log_unit[map_key] = refValue
						if map_key not in log_unit and self.key not in log_unit:
							# print(log_unit)
							self.insertOthers("no_key",log_unit)
						else:
							if content in self.contents:
								parent = self.getContent(content,log_unit)
								if not parent:
									self.insertOthers(content,log_unit)
									continue
								else:
									if self.key not in parent and self.key in log_unit:
										parent[self.key] = log_unit[self.key]
									elif self.key in log_unit and not parent[self.key] == log_unit[self.key]:
										self.insertOthers(content,log_unit)
										continue
									if register_cfg["type"] == "list":
										if name not in parent:
											parent[name] = []
										self.insertByTime(parent[name],log_unit)
									else:
										parent[name] = log_unit
							else:
								self.insertOthers(content, log_unit)
								continue


					if "register" not in log_unit:
						log_unit["register"] = []
					log_unit["register"].append(register)


	def setupException(self,err_info):
		if self.current_error:
			if "stacks" not in self.current_error:
				self.current_error["stacks"] = {}
			if err_info["name"] not in self.current_error["stacks"]:
				self.current_error["stacks"][err_info["name"]] = {}
			self.current_error["stacks"][err_info["name"]] = {"name": err_info["reason"]}
			self.current_error_index = self.current_error["stacks"][err_info["name"]]
			# if "thread" not in self.current_error:
			# 	print(err_info)
			if self.current_error["thread"] in self.errors:
				self.current_error["stacks"][err_info["name"]]["reason"] = err_info["reason"]

			if err_info["name"] not in self.stacks:
				self.stacks[err_info["name"]] = {}
			self.current_stack = self.stacks[err_info["name"]]
			return err_info["name"]

	def matchLine(self, line,cfg,line_info,global_cfg):
		for match_cfg in cfg:
			if matchLine(line,match_cfg):
				if "extract" in match_cfg:
					extract_cfgs = match_cfg["extract"]
					for name in extract_cfgs:
						extract_cfg = extract_cfgs[name]
						extractLine(line, line_info, name, extract_cfg, global_cfg)
				return True
		return False

	def processError(self, line):
		err_info ={}
		# if line.find("[info ") < 0:
		# 	print(line)
		if self.matchLine(line,self.log_cfg["exception"]["matches"],err_info,self.log_cfg["extract"]):
			if "name" in err_info:
				self.setupException(err_info)
		elif self.current_error and "exception_end" in self.log_cfg and \
			self.matchLine(line,self.log_cfg["exception_end"]["matches"],self.current_error_index,self.log_cfg["extract"]):
			self.current_stack_index = None

		elif self.current_error_index and self.matchLine(line,self.log_cfg["exception_msg"]["matches"],err_info,self.log_cfg["extract"]):
			if "index" not in self.current_error_index:
				if "message" in err_info:
					code_index = err_info["message"]
				else:
					code_index = line.strip(" \n")
				self.current_error_index["index"] = code_index
				if code_index not in self.current_stack:
					self.current_stack[code_index] = []
					self.current_stack_index = self.current_stack[code_index]
				else:
					self.current_stack_index = None
			if not self.current_stack_index == None:
				self.current_stack_index.append(err_info["message"])

	def parseLineError(self, line, thread_no, line_info):
		error_cfg = self.log_cfg["error"]
		err_info = {"thread":thread_no}
		if self.matchLine(line, error_cfg["matches"], err_info, self.log_cfg["extract"]):
			self.errors[thread_no] = err_info
			self.current_error = err_info
			line_info["error"] = err_info
			err_info["msg"] = line_info["msg"]
			err_info["log_time"] = line_info["log_time"]
			if "main" in self.log_cfg["thread"] and thread_no.startswith(self.log_cfg["thread"]["main"]) and err_info["level"] == "ERROR":
				err_info["level"] = "FATAL"



	def getCurrentThread(self,line,line_info):
		log_time = line_info["log_time"]
		if self.thread_no in self.log_units_history:
			history = self.log_units_history[self.thread_no]
			index = len(history) - 1
			while index >= 0:
				item = history[index]
				if item["start_time"] > log_time:
					index -= 1
				else:
					self.log_units[self.thread_no] = item
					return

	def processContent(self,content):
		if content not in self.log_cfg["no_key_contents"] and content in self.contents:
			for index in self.contents[content]["index"]:
				item = self.contents[content][index]
				if "sub_index" in self.log_cfg["contents"][content]:
					for sub_index in item["index"]:
						log_units = item[sub_index]
						for log_unit in log_units:
							self.register(log_unit)
				else:
					for log_unit in item:
						self.register(log_unit)
		elif content in self.contents:
			for item in self.contents[content]:
				if not item == "index":
					item_index_list = self.contents[content][item]["index"]
					for index in item_index_list:
						log_units = self.contents[content][item][index]
						for log_unit in log_units:
							self.register(log_unit)

	def distribute(self,content):
		distributed = self.log_cfg["contents"][content]["distributed"]
		if content in self.contents:
			for item in self.contents[content]:
				if not distributed == self.key:
					key = self.maps[distributed][item[distributed]]
				else:
					key = item[self.key]
				session =  self.getSession(key,item["log_time"])
				if session:
					if content not in session:
						session[content] = [item]
					else:
						session[content].append(item)
				else:
					session = self.getSession(key, item["log_time"])
					self.insertOthers(content,item)


		# content = log_unit["type"]
		# self.register(log_unit)

	def parseLog(self):
		self.setupThread()
		for thread_index in self.threads:
			self.startThread(thread_index)
			for sub_index in self.threads[thread_index]["index"]:
				thread_data = self.threads[thread_index][sub_index]
				time_list = [key for key in thread_data.keys()]
				time_list.sort()
				for time_index in time_list:
					line_list = thread_data[time_index]
					for line in line_list:
						self.thread_no = line["thread"]
						line_info = {}
						thread_type = self.getThreadType(line, line_info)
						if not thread_type == "":
							self.processThread(line,thread_type,line_info)
			self.endThread()
			if self.unknown:
				self.setUnknown(self.unknown)
				self.injectContent("unknown", self.unknown)
				self.unknown = None

		# #
		# contents_file = open("contents.json","w",encoding="utf-8")
		# json.dump(self.contents,contents_file,indent=4)
		# contents_file.close()
		# sessions_file = open("sessions.json","w",encoding="utf-8")
		# json.dump(self.sessions,sessions_file,indent=4)
		# sessions_file.close()
		# maps_file = open("maps.json","w",encoding="utf-8")
		# json.dump(self.maps,maps_file,indent=4)
		# maps_file.close()


		# contents_file = open("contents.json","r",encoding="utf-8")
		# self.contents = json.load(contents_file)
		# session_file = open("sessions.json","r",encoding="utf-8")
		# self.sessions = json.load(session_file)
		# maps_file = open("maps.json","r",encoding="utf-8")
		# self.maps =  json.load(maps_file)
		unknowns = {}
		if "unknown" in self.contents:
			for start_time in self.contents["unknown"]["index"]:
				unknown_item_list = self.contents["unknown"][start_time]
				for unknown_item in unknown_item_list:
					if self.key in unknown_item and unknown_item[self.key] not in self.sessions:
						if unknown_item[self.key] not in unknowns:
							unknowns[unknown_item[self.key]] = []
						unknowns[unknown_item[self.key]].append(unknown_item)
		total = 0
		for key in unknowns:
			# print(key + ":" + str(len(unknowns[key])))
			total += len(unknowns[key])


		contents = [content for content in self.log_cfg["contents"] if not content in self.log_cfg["no_key_contents"] and not content == "session" and \
		            not "distributed" in self.log_cfg["contents"][content]]
		for content in contents:
			if "distributed" not in self.log_cfg["contents"][content]:
				self.processContent(content)
		for content in self.log_cfg["no_key_contents"]:
			self.processContent(content)

		contents = [content for content in self.log_cfg["contents"] if "distributed" in self.log_cfg["contents"][content]]
		for content in contents:
			self.distribute(content)



		# 	for unit_type in self.contents[content]:
		# 		others = self.others[content][unit_type]
		# 		for thread_no in others:
		# 			for unit_time in others[thread_no]:
		# 				if not unit_time == "index":
		# 					log_unit = others[thread_no][unit_time]
		# 					self.register(log_unit,final=True)
		#
		#
		# for thread_no in self.log_units:
		# 	self.register(self.log_units[thread_no])

		# self.dumpSessions()


		self.processCategories()
		self.dumpData("categories")


		self.dumpData("stacks")
		# self.dumpData("apis")

		self.dumpData("others")
		self.dumpUnknown()

		if "outputs" in self.log_cfg:
			for item in self.log_cfg["outputs"]:
				self.dumpData(item, zip=False)

	def getSessions(self):
		for key in self.current_session:
			key_session = self.current_session[key]
			if not key in self.sessions:
				self.sessions[key] = {"index":[]}
			self.injectByTime(self.sessions[key],key_session)


	def dumpStacks(self):
		folder = self.log_file.split(".")[0]
		if not os.path.exists(folder):
			os.mkdir(folder)

		stackFile = folder + "/stacks.json"
		stack_file = open(stackFile,"w", encoding="utf-8")
		json.dump(self.stacks,stack_file,indent=4)
		stack_file.close()

	def dumpUnknown(self):
		folder = self.log_file.split(".")[0]
		if not os.path.exists(folder):
			os.mkdir(folder)
		folder = folder + "/unknown"
		if not os.path.exists(folder):
			os.mkdir(folder)


		for thread in self.unknown_units:
			new_thread = thread.strip(" ():,")
			if new_thread.find("(") > 0:
				new_thread = thread.split("(")[0].strip(" ")
			new_thread = new_thread.replace(":","_").replace("%","_")
			thread_folder = folder + "/" + new_thread
			zipfolder = None
			zip_files = []
			for log_unit in self.unknown_units[thread]:
				log_unit["thread"] = new_thread
				if "error" in log_unit:
					if not os.path.exists(thread_folder):
						os.mkdir(thread_folder)
					unknown_json = thread_folder +"/" + str(log_unit["id"]) + ".json"
					json_file = open(unknown_json,"w",encoding="utf-8")
					json.dump(log_unit,json_file,indent=4)
					json_file.close()
					if not zipfolder:
						zipname = thread_folder + ".zip"
						zipfolder = zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED, compresslevel=9)
					if not unknown_json in zip_files:
						zipfolder.write(unknown_json)
						zip_files.append(unknown_json)
					os.remove(unknown_json)
			if os.path.exists(thread_folder):
				os.rmdir(thread_folder)

	def dumpSession(self, session):
		folder = self.log_file.split(".")[0]
		if not os.path.exists(folder):
			os.mkdir(folder)
		if "id" not in session:
			self.setSession("session",session)
			# print(session)
		session_id = session["id"]
		folder += "/" + str(session_id)
		if not os.path.exists(folder):
			os.mkdir(folder)

		# if "thread" in session:
		# 	thread_file = folder + "/session.log"
		# 	self.dumpThread(session,thread_file)

		# if "sub_items" in self.log_cfg:
		# 	for item in self.log_cfg["sub_items"]:
		# 		if item in session:
		# 			for log_unit in session[item]:
		# 				index = log_unit["id"]
		# 				worker_file = folder + "/" + item + str(index) + ".log"
		# 				self.dumpThread(log_unit,worker_file)

		json_file = folder + "/session.json"
		jsonFile = open(json_file, "w",  encoding="utf-8")
		json.dump(session,jsonFile,indent=4)
		jsonFile.close()
		zipname = folder + ".zip"
		zipfile.ZipFile(zipname,"w",zipfile.ZIP_DEFLATED,compresslevel=9).write(json_file)
		os.remove(json_file)
		os.rmdir(folder)


	def dumpThread(self, thread, file_name):
		threadFile = open(file_name, "w", encoding="utf-8")
		threadFile.writelines(thread["msg"])
		threadFile.close()

	def getStacksName(self, error):
		if "stacks" in error:
			exception_name = None
			stack = None
			for exception in error["stacks"]:
				if "caused_by" not in error["stacks"][exception]:
					stack = error["stacks"][exception]
					break
				if not exception_name or len(error["stacks"][exception]["name"]) < len(exception_name):
					exception_name = error["stacks"][exception]["name"]
					stack = error["stacks"][exception]

			if "name" in stack:
				error["name"] = stack["name"]
			elif "caused_by" in stack:
				error["name"] = stack["name"]
			return stack



	def assignCategory(self, error):
		category = None
		if "log_file" not in error:
			error["log_file"] = self.name
		if "api" in error:
			if type(error["api"]) == list:
				print("*** unexpected error apis as list :" + str(error["api"]))
			category  = self.findCategory(error["api"])


		if "stacks" in error:
			stack  = self.getStacksName(error)
			if stack and not category:
				category = self.findCategory(error["name"])
				if not category and "caused_by" in stack:
					name = stack["caused_by"]
					if "name" not in error:
						error["name"] = stack["caused_by"]
					category = self.findCategory(name)
				if not category:
					if "index" in stack:
						index = stack["index"]
						category = self.findCategory(index)
					# if category:
					# 	break
			if "filename" in error and not category:
				category = self.findCategory(error["filename"])
		if "name" not in error:
			if "api" in error:
				category = self.findCategory(error["api"])
				# error["name"] = error["api"]

			if "msg" not in error:
				print(error)
			error["name"] = " ".join(error["msg"].split(")", 1)[1].strip(" \n").split(" ")[:10])

		if error["level"] == "FATAL":
			category = "fatal"

		if not category:
			category = self.findCategory(error["name"])


		if not category:
			category = "others"
		if category not in self.categories:
			self.categories[category] = {}
		errors = self.categories[category]
		if "name" in error:
			if error["name"] not in errors:
				errors[error["name"]] = []
			errors[error["name"]].append(error)
		# else:
		# 	print(error)

	def findCategory(self, target):
		if "categories" in self.log_cfg:
			cfg = self.log_cfg["categories"]
			for key in cfg:
				if target.lower().find(key) >= 0:
					if cfg[key] not in self.categories:
						self.categories[cfg[key]] = {}
					return cfg[key]


	def processCategories(self):
		self.categories = {"others":{}}
		for error in self.error_list:
			if "level" in error and error["level"] in ["ERROR","FATAL"]:
				self.assignCategory(error)

	def dumpStacks(self):
		folder = self.log_file.split(".")[0]
		if not os.path.exists(folder):
			os.mkdir(folder)

		stackFile = folder + "/stacks.json"
		stack_file = open(stackFile,"w", encoding="utf-8")
		json.dump(self.stacks,stack_file,indent=4)
		stack_file.close()

	def dumpData(self,data_name,zip=True):
		if hasattr(self,data_name):
			folder = self.log_file.split(".")[0]
			if not os.path.exists(folder):
				os.mkdir(folder)

			jsonFile = folder + "/" + data_name + ".json"
			json_file = open(jsonFile, "w", encoding="utf-8")
			json.dump(getattr(self,data_name),json_file,indent=4)
			json_file.close()
			if zip:
				zip_file = folder + "/" + data_name + ".zip"
				zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED, compresslevel=9).write(jsonFile)
				os.remove(jsonFile)


	def dumpCategories(self):
		folder = self.log_file.split(".")[0]
		if not os.path.exists(folder):
			os.mkdir(folder)

		stackFile = folder + "/errors.json"
		stack_file = open(stackFile,"w", encoding="utf-8")
		json.dump(self.categories,stack_file,indent=4)
		stack_file.close()

	def getEndTime(self, log_unit):
		if "msg" in log_unit and len(log_unit["msg"]) > 0:
			index = log_unit["msg"][-1].find(self.test_date)
			log_unit["lines"] = len(log_unit["msg"])
			log_time = log_unit["msg"][-1][index:index + self.log_cfg["log_time"]]

			return log_time


	def setAPIs(self,log_unit,end_time):
		log_time = self.getEndTime(log_unit)
		if log_time:
			log_unit["end_time"] = log_time
			if "name" in log_unit and "start_time" in log_unit and "error" not in log_unit:
				try:
					endTime = datetime.datetime.strptime(log_unit["end_time"], "%Y-%m-%dT%H:%M:%S,%f")
					# if len(log_unit["start_time"]) < 20:
					# 	print(log_unit)
					startTime = datetime.datetime.strptime(log_unit["start_time"], "%Y-%m-%dT%H:%M:%S,%f")
					duration = (endTime - startTime).seconds
					log_unit["duration"] = duration
					log_unit["num"] = len(log_unit["msg"])
					if log_unit["name"] not in self.apis:
						self.apis[log_unit["name"]] = {"total": duration, "num": 1, "avg": duration,
						                               "lines": log_unit["lines"]}
					else:
						self.apis[log_unit["name"]]["total"] += duration
						self.apis[log_unit["name"]]["num"] += 1
						self.apis[log_unit["name"]]["lines"] += log_unit["lines"]
						self.apis[log_unit["name"]]["avg"] = self.apis[log_unit["name"]]["total"] / \
						                                     self.apis[log_unit["name"]]["num"]
				except Exception as e:
					print(e)

		if not end_time or (log_time and log_time > end_time):
			end_time = log_time
		return end_time

	def dumpSessions(self):
		# self.getSessions()
		folder = self.log_file.split(".")[0]
		if not os.path.exists(folder):
			os.mkdir(folder)


		for key in self.sessions:
			sessions = self.sessions[key]
			session_times = sessions["index"]
			length = len(session_times)
			for i in range(length):
				start_time = session_times[i]
				next_session = None
				if i < length -1:
					next_session = sessions[session_times[i+1]]
				session = self.sessions[key][start_time]
				end_time = self.getEndTime(session)
				if "errors" in session or "error" in session:
					self.setLogUnitError(session)
					self.dumpSession(session)
				if "sub_items" in self.log_cfg:
					for item in self.log_cfg["sub_items"]:
						if item in session:
							index = 0
							for log_unit in session[item]:
								if next_session and log_unit["start_time"] > next_session["start_time"]:
									self.register(log_unit, next_session)
								else:
									end_time = self.setAPIs(log_unit,end_time)
									index += 1
								if "error" in log_unit:
									self.setLogUnitError(log_unit)
							if index < len(session[item]) - 1:
								session[item] = session[item][:index]
				else:
					end_time = self.setAPIs(session,end_time)
				session["end_time"] = end_time
				if "sub_items" in self.log_cfg:
					keys = [key_name for key_name in session]
					for key_name in keys:
						if key_name in self.log_cfg["sub_items"]:
							continue
						if key_name in ["id","name","start_time","end_time"]:
							continue
						session.pop(key_name)


		for key in self.apis:
			api = self.apis[key]
			api["effect_total"] = api["total"]
			api["effect_num"] = api["num"]

		for key in self.sessions:
			for start_time in self.sessions[key]["index"]:
				session = self.sessions[key][start_time]
				if "sub_items" in self.log_cfg:
					for item in self.log_cfg["sub_items"]:
						if item in session:
							for log_unit in session[item]:
								if not log_unit["session"] == session["id"]:
									print(log_unit)
								if "name" in log_unit and not "error" in log_unit:
									if log_unit["name"] not in self.apis:
										pass
										# print(log_unit)
									else:
										api= self.apis[log_unit["name"]]
										# if "msg" not in log_unit:
										# 	print(log_unit)
										if len(log_unit["msg"]) > api["lines"] / api["num"] * 1.2 and "error" not in log_unit and "duration" in log_unit:
											# print(log_unit)
											api["effect_total"]  -= log_unit["duration"]
											api["effect_num"] -= 1
								keys = [key_name for key_name in log_unit]
								for key_name in keys:
									if key_name == "error":
										log_unit["error"] = True
									if key_name not in ["id","name","start_time","end_time","error"]:
										log_unit.pop(key_name)
				else:
					if "name" in session and "error" not in session:
						if session["name"] in self.apis:
							api = self.apis[session["name"]]
							# if "msg" not in session:
							# 	print(session)
							if len(session["msg"]) > api["lines"] / api["num"] * 1.2 and "error" not in session:
								# print(session)
								api["effect_total"] -= session["duration"]
								api["effect_num"] -= 1
						# else:
						# 	print(session)
					keys = [key_name for key_name in session.keys()]
					for key_name in keys:
						if key_name not in ["id", "name", "start_time", "end_time", "error",self.key,"thread"]:
							session.pop(key_name)

		for key in self.apis:
			api = self.apis[key]
			api["effect_avg"] = api["effect_total"]/api["effect_num"]

		# sessionFile = folder + "/session.json"
		# json_file = open(sessionFile,"w", encoding="utf-8")
		# json.dump(self.sessions,json_file,indent=4)
		# json_file.close()
		self.dumpData("apis")







if __name__ == "__main__":
	# log_cfg = {"thread":{"left":"[","right":"]"},
	#            "contents":{"session":{"matches":[{"include":{"must":["security.PortalCasAuthenticationProvider (line 56)"],
	#
	#                                                          "extract":{"user":{"pattern":{"selector":{"User ":1},"splitter":" ","value":"<left>"}}}}}]}}}
	jsonCfg = open("portal_log.json","r",encoding="utf-8")
	log_cfg = json.load(jsonCfg,strict=False)
	cryptLog = LogParser("qa2_portal.log","2024-04-29",log_cfg)
	maps_file = open("qa2_crypto/maps.json","r",encoding="utf-8")
	maps = json.load(maps_file)
	cryptLog.setKeysMap(maps)
	cryptLog.parseLog()
	# cryptLog.dumpData("sessions")
	# cryptLog.dumpSessions()
	res = {}
	for log_unit in cryptLog.others:
		if "name" not in log_unit:
			print(log_unit)
		else:
			if log_unit["name"] not in res:
				res[log_unit["name"]] = []
			res[log_unit["name"]].append(log_unit)
	print(res)