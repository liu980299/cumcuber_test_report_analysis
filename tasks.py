import pymsteams

teams_message = pymsteams.connectorcard("https://reedelsevier.webhook.office.com/webhookb2/96390274-7d2e-4cb7-aeb6-996af8de4b00@9274ee3f-9425-4109-a27f-9fb15c10675d/IncomingWebhook/1b8da765b0f742528c5d8105b37d08cb/41f1254c-9228-4a11-8d82-43dbd5c3291d")

# teams_message.payload={
#     "@type":"MessageCard",
#     "@context":"http://schema.org/extensions",
#     "title": "Test Summary",
#      "text": "Hello <at>Liu, Xiang</at> **Total : 1004 <strong style='color:red;'>Failed : 25</strong>** Version : 14.4.0-355 Portal : https://portal-qa1.qa.threatmetrix.com\n\n<H2>Please check auto test results on Workspace:</H2><a href='.'>.</a>",
#     "potentialAction": [
#         {
#             "@context": "http://schema.org",
#             "@type": "ViewAction",
#             "name": "Please check result on Workspace",
#             "target": [
#                 "."
#             ]
#         }
#     ],
#     "sections": [
#         {
#             "title": "# **JOB : [User-Key-Management-QA1](https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/User-Key-Management-QA1/Cluecumber_20Test_20Report/)**",
#             "text": "\n\n<ul><strong style='color:green;'>  Congratulation! No feature failed in this job! </strong></ul>"
#         },
#         {
#             "title": "# **JOB : [release-canary-test](https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/Cluecumber_20Test_20Report/)**",
#             "text": "\n\n<ul><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_29.html'>Audit related feature (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_23.html'>Check FCC Integration Tests (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_17.html'>FCC Case management scenarios from Workspace (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_2.html'>Forensics Query Test (0/2)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_28.html'>Org interception Tests (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_39.html'>Orgnization CRUD functionalities (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_10.html'>Role CRUD functionalities (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test/1026//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_4.html'>User CRUD functionalities (0/1)</a></li></ul>"
#         },
#         {
#             "title": "# **JOB : [release-canary-test-2](https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/Cluecumber_20Test_20Report/)**",
#             "text": "\n\n<ul><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_5.html'>Alerts functionalities (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_31.html'>BehavioralBiometrics functionalities (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_27.html'>Forensics_react Query Test (0/4)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_1.html'>In-place update features for first class connectors (0/4)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_2.html'>Lists Test (0/3)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_30.html'>Orgnization CRUD functionalities (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_3.html'>Policy list functions (0/1)</a></li><li><a href='https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/release-canary-test-2/757//QA1_20Cucumber_20Test_20Report/pages/feature-scenarios/feature_10.html'>SAML log in (0/1)</a></li></ul>"
#         }
#     ],
#     "themeColor": "E81123",
#     "msteams":{
#         "entities": [
#             {
#                 "type": "mention",
#                 "text": "<at>Xiang Liu</at>",
#                 "mentioned": {
#                     "id": "LiuXia01@risk.regn.net",
#                     "name": "Liu, Xiang"
#                 }
#             }
#         ]
#     }
# }
teams_message.payload = {
    "type": "message",
    "content":{
        "body": [
            {
                "type": "TextBlock",
                "text": "Hello <at>Xiang Liu</at>\n\n# **JOB : [User-Key-Management-QA1](https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/User-Key-Management-QA1/Cluecumber_20Test_20Report/)**"
            }
        ]

    },
    "attachments": [
        {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "Hello <at>Xiang Liu</at>\n\n# **JOB : [User-Key-Management-QA1](https://jenkins106.cd.sac.int.threatmetrix.com/job/qa/job/portal-tests/job/User-Key-Management-QA1/Cluecumber_20Test_20Report/)**"
                }

            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.0",
            "msteams": {
                "entities": [
                     {
                        "type": "mention",
                        "text": "<at>Xiang Liu</at>",
                        "mentioned": {
                            "id": "LiuXia01@risk.regn.net",
                            "name": "Liu, Xiang"
                        }
                    }
                ]
            }
        }
     }
]
}
teams_message.send()