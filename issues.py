import re

from jira import JIRA

jira = JIRA(server="https://jira.cd.sac.int.threatmetrix.com/",token_auth="NjMyMDg5NDkzMTg0OiQ8z+kC4tyrCbZv2frdWsNB3Crt")
issue_meta = jira.createmeta_issuetypes("PORTAL")
meta = jira.createmeta_fieldtypes("QA",1 )
users = jira.search_users("xiang")
print(meta)
projects = jira.projects()
for project in projects:
    if project.key == "PORTAL":
        components = jira.project_components("PORTAL")
        versions = jira.project_versions("PORTAL")
        print(components)
print(projects)