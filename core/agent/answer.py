"""Rule checks for procedural model prose. These are guards, not semantic proof."""
import re


def compact(text):
    return re.sub(r'[\s*`#]','',text).replace('：',':')


def numbers(text):
    return set(re.findall(r'\d+(?::\d+|\.\d+)?',compact(text)))


EVENTS={'borrow':r'停止借还|停止图书借还|停止办理|归还|还书|借还',
        'close':r'闭馆|关门|关闭','open':r'开馆|开门'}


def time_events(text,task=''):
    pairs=set()
    for clause in re.split(r'[，,。；;\n]',compact(text)):
        # Explicit arrival preferences are not opening or service deadlines.
        attributed=bool(re.search(r'按(?:你|您)(?:的计划|提供的时间|说的时间)',clause))
        policy=bool(re.search(r'停止|截止|闭馆|关门|开门|开馆|开放|照常|仍可',clause))
        if attributed and not policy and numbers(clause).issubset(numbers(task)):
            continue
        times=list(re.finditer(r'\d{1,2}:\d{2}',clause))
        events=[(kind,m.start()) for kind,pattern in EVENTS.items() for m in re.finditer(pattern,clause)]
        for kind,pos in events:
            if times:
                nearest=min(times,key=lambda t:min(abs(t.start()-pos),abs(t.end()-pos)))
                if min(abs(nearest.start()-pos),abs(nearest.end()-pos))<16:pairs.add((nearest.group(),kind))
    return pairs


def check_steps(steps,facts,task):
    errors=[]
    for index,step in enumerate(steps):
        text=compact(step.instruction)
        if not text:
            errors.append(f'步骤{index+1}内容为空');continue
        if re.search(r'(?:已|已经).{0,8}(?:提交|预约|支付|报名|发送|取消|办理成功)|(?:提交|预约|支付|报名|发送|取消)(?:成功|完成)',text):
            errors.append(f'步骤{index+1}不能声称只读工具已经代办或提交');continue
        refs=step.evidence_ids
        if any(k not in facts for k in refs):
            errors.append(f'步骤{index+1}引用了本次未返回的证据');continue
        support=compact('\n'.join(facts[k]['text'] for k in refs))
        # User-provided times can be repeated as preferences, not used as policy evidence.
        if not numbers(text).issubset(numbers(support)|numbers(task)):
            errors.append(f'步骤{index+1}含无依据的数字或时间');continue
        if time_events(text,task)-time_events(support):
            errors.append(f'步骤{index+1}的时间与业务事项不对应');continue
        if re.search(r'\[e?\d+\]|https?://',text):
            errors.append(f'步骤{index+1}请使用evidence_ids字段关联引用，不在文字中编写编号或网址');continue
        # Check each clause: an unrelated "先确认" must not excuse an asserted fact.
        factual_parts=[]
        for clause in re.split(r'[，,。；;\n]',text):
            pending=bool(re.search(r'待确认|待核实|尚未|暂未|未查到|无法确认|先确认|再确认|确认.*后|核实.*后|请问|是否|建议.*咨询',clause))
            factual=bool(re.search(r'开放|开门|闭馆|关门|停止借还|截止|电话|手机号|位于|地址|免费|收费|必须|不得|禁止|允许|照常|无需预约|需要预约|携带|出示|在.{0,10}[楼层]',clause))
            if factual and not pending:factual_parts.append(clause)
        if factual_parts:
            if not refs:
                errors.append(f'步骤{index+1}的规定或地点陈述缺少引用');continue
            sensitive=('周末','周六','周日','工作日','节假日','免费','无需预约','需要预约','不得','禁止','必须')
            factual_text='，'.join(factual_parts)
            if any(term in factual_text and term not in support for term in sensitive):
                errors.append(f'步骤{index+1}扩写了原文没有的适用条件');continue
            # Require substantive words to be supported, not just a number appearing somewhere.
            stripped=re.sub(r'建议|请|尽量|提前|注意|先|再|可以|完成|办理|避免|错过|前往|到|从|的|在|于|是|将|并|与|和|按|后|前|\d+[:.]?\d*','',factual_text)
            grams={stripped[i:i+2] for i in range(len(stripped)-1) if re.fullmatch(r'[\u4e00-\u9fff]{2}',stripped[i:i+2])}
            if grams and sum(g in support for g in grams)/len(grams)<.7:
                errors.append(f'步骤{index+1}的事实措辞超出所引用原文')
    return errors[:4]


def render_steps(steps,citation_numbers):
    lines=[]
    for i,step in enumerate(steps,1):
        refs=''.join(f'[{citation_numbers[k]}]' for k in dict.fromkeys(step.evidence_ids) if k in citation_numbers)
        lines.append(f'{i}. {step.instruction.strip()}'+(' '+refs if refs else ''))
    return '\n'.join(lines)
