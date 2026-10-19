"""Prove exactly one arithmetic extraction, preserving every other module AST."""
import ast,copy

def same(a,b):return ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
def statements(nodes):return ast.Module(body=nodes,type_ignores=[])
def method(module):
    cls=next(n for n in module.body if isinstance(n,ast.ClassDef)and n.name=='DartValueFactorAdapter')
    return next(n for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='factor_frame')
def prove(before,after):
    old=ast.parse(before);new=ast.parse(after);a=method(old);b=method(new)
    helpers=[n for n in new.body if isinstance(n,ast.FunctionDef)and n.name=='calculate_value_factors']
    assert len(helpers)==1,'EXACTLY_ONE_DECLARED_HELPER_REQUIRED';helper=helpers[0]
    assert not any(isinstance(n,ast.FunctionDef)and n.name==helper.name for n in old.body)
    assert not helper.decorator_list and not helper.args.vararg and not helper.args.kwarg and not helper.args.kwonlyargs and not helper.args.defaults
    assert [x.arg for x in helper.args.args]==['raw','cross_section','signal','period_policy']
    cut=next(i for i,n in enumerate(a.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='marcap'for t in n.targets))
    assert same(statements(a.body[:cut]),statements(b.body[:-1])),'PROVIDER_GATE_OR_SOURCE_PATH_CHANGED'
    call=ast.parse('return calculate_value_factors(raw, cross_section, signal, self.period_policy)').body[0]
    assert same(b.body[-1],call),'ONLY_EXPLICIT_ORIGINAL_INPUTS_ALLOWED'
    class Policy(ast.NodeTransformer):
        def visit_Attribute(self,node):
            if isinstance(node.value,ast.Name)and node.value.id=='self'and node.attr=='period_policy':return ast.Name(id='period_policy',ctx=node.ctx)
            return self.generic_visit(node)
    original=Policy().visit(copy.deepcopy(statements(a.body[cut:])))
    body=helper.body[1:]if isinstance(helper.body[0],ast.Expr)and isinstance(helper.body[0].value,ast.Constant)and isinstance(helper.body[0].value.value,str)else helper.body
    assert same(original,statements(body)),'ARITHMETIC_OR_PERIOD_POLICY_CHANGED'
    new.body.remove(helper);b.body=copy.deepcopy(a.body)
    assert same(old,new),'UNDECLARED_MODULE_CHANGE'
    return dict(status='PASS_EXACT_AST_EXTRACTION',provider_gate_and_source_path='UNCHANGED',arithmetic_and_period_policy='UNCHANGED',all_other_module_AST='UNCHANGED',financial_or_strategy_goldens_changed=False)
