import unittest
from core.agent.runtime import AgentRuntime

FACT={'text':'图书馆工作日21:30停止借还，22:00闭馆。','source':'library','title':'借还时间'}
CALL={'action':'tool','tool':'search_knowledge','arguments':{'query':'图书馆借还时间'}}


class AgentPlanTests(unittest.TestCase):
    def run_plan(self,decision,tail=None):
        actions=[CALL,decision]+(tail or [])
        self.messages=[]
        def planner(messages,remaining):
            self.messages.append(messages)
            return actions.pop(0)
        return AgentRuntime(planner,{'search_knowledge':lambda args,t:{'status':'ok','facts':[FACT]}}).run('从南大门出发，先还书，再咨询选课')

    def test_natural_action_plan_distinct_from_evidence_dump(self):
        r=self.run_plan({'action':'finish','evidence_ids':['e1'],'plan':[
            {'instruction':'建议先去图书馆还书，避免错过借还业务时间。','evidence_ids':['e1']},
            {'instruction':'再确认选课咨询的办理地点后前往。','evidence_ids':[]}
        ],'missing':['教务处办公时间尚待核实']})
        self.assertIn('办理建议',r['answer'])
        self.assertIn('1. 建议先去图书馆还书',r['answer'])
        self.assertIn('2. 再确认选课咨询',r['answer'])
        self.assertIn('[1]',r['answer'])
        self.assertNotIn('已核实的信息（按模型选择',r['answer'])
        self.assertEqual(r['agent']['plan_status'],'checked')

    def test_invented_time_is_rejected_then_repaired(self):
        bad={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'建议20:00到图书馆还书。','evidence_ids':['e1']}]}
        good={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'建议先去图书馆还书。','evidence_ids':['e1']}]}
        r=self.run_plan(bad,[good])
        self.assertNotIn('20:00',r['answer'])
        self.assertEqual(r['agent']['plan_status'],'checked')
        self.assertTrue(any(x['status']=='plan_rejected' for x in r['agent']['trace']))

    def test_wrong_time_event_binding_rejected(self):
        bad={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'图书馆22:00停止借还。','evidence_ids':['e1']}]}
        r=self.run_plan(bad,[bad])
        self.assertNotIn('图书馆22:00停止借还',r['answer'])
        self.assertEqual(r['agent']['plan_status'],'fallback')

    def test_unreferenced_phone_and_unknown_citation_rejected(self):
        bad={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'先拨打02712345678预约。','evidence_ids':['e999']}]}
        r=self.run_plan(bad,[bad])
        self.assertNotIn('02712345678',r['answer'])
        self.assertTrue(r['partial'])

    def test_suggestion_cannot_invent_opening_policy(self):
        bad={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'建议直接去教务处，周末照常开放。','evidence_ids':['e1']}]}
        r=self.run_plan(bad,[bad])
        self.assertNotIn('周末照常开放',r['answer'])
        self.assertEqual(r['agent']['plan_status'],'fallback')

    def test_pending_phrase_does_not_hide_an_unrelated_claim(self):
        bad={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'先确认出发地点，教务处周末照常开放。','evidence_ids':['e1']}]}
        r=self.run_plan(bad,[bad])
        self.assertNotIn('教务处周末照常开放',r['answer'])
        self.assertEqual(r['agent']['plan_status'],'fallback')

    def test_agent_mode_requires_plan_instead_of_silent_evidence_dump(self):
        actions=[CALL,{'action':'finish','evidence_ids':['e1']},
                 {'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'建议先去图书馆办理还书。','evidence_ids':['e1']}]}]
        r=AgentRuntime(lambda m,t:actions.pop(0),{'search_knowledge':lambda a,t:{'status':'ok','facts':[FACT]}},require_plan=True).run('还书')
        self.assertIn('办理建议',r['answer'])
        self.assertTrue(any(t['status']=='plan_rejected' for t in r['agent']['trace']))

    def test_readonly_agent_cannot_claim_to_have_submitted_or_booked(self):
        bad={'action':'finish','evidence_ids':['e1'],'plan':[{'instruction':'已帮你提交选课申请，可以直接前往。','evidence_ids':['e1']}]}
        r=self.run_plan(bad,[bad])
        self.assertNotIn('已帮你提交',r['answer'])
        self.assertEqual(r['agent']['plan_status'],'fallback')

    def test_explicit_user_arrival_time_is_not_a_policy_cutoff(self):
        from core.agent.answer import check_steps
        from core.agent.contracts import PlanStep
        row=PlanStep(instruction='按你的计划20:00去图书馆还书。',evidence_ids=['e1'])
        self.assertEqual(check_steps([row],{'e1':FACT},'我计划20:00去图书馆还书'),[])
        wrong=PlanStep(instruction='按你的计划，图书馆20:00停止借还。',evidence_ids=['e1'])
        self.assertTrue(check_steps([wrong],{'e1':FACT},'我计划20:00去图书馆还书'))

if __name__=='__main__':unittest.main()
