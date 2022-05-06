from . import esprima
from .types import BasicBlock, CFG, CONTROL
from .draw_cfg import draw_cfg

NODE_TO_IGNORE = ['EmptyStatement', 'DebuggerStatement','Super','Literal','Identifier','ThisExpression','RestElement',
                  'ExportAllDeclaration','ExportDefaultDeclaration','ExportNamedDeclaration','ExportSpecifier',
                  'ImportSpecifier','TemplateLiteral']

NODE_TO_ADD_IN_VISIT = ['BlockStatement','SwitchStatement','CallExpression', 'IfStatement', 'ConditionalExpression'
    ,'VariableDeclaration','VariableDeclarator','ExpressionStatement','SequenceExpression','Literal','Identifier'
    ,'BreakStatement','ReturnStatement','TryStatement','ThrowStatement','MemberExpression','WhileStatement'
    ,'DoWhileStatement','ForStatement','ForInStatement','ForOfStatement','LogicalExpression']


def get_v8_offset(node):
    # return node.range[0] + node.loc.start.line-1
    return node.range[0]


class JSCFGBuilder:
    def __init__(self):
        self.cfgs = []
        self.ast = None
        self.build_queue = []
        self.cur_cfg = None
        self.switchloop_stack = None
        self.try_stack = None
        self.prev_try_final_last_bb = None
        self.prev_logical_right_bb = None
        self.prev_logical_merge_bb = None
        self.handle_loop_condition = True
        self.label_list = []

    def build(self, code=None, filename=None, script_id=-1):
        if filename:
            with open(filename, 'r') as f:
                code = f.read()

        # code = code.replace('\n', '  ')

        # parse script
        ast = esprima.parseScript(code, range=True, loc=True, tolerant=True)
        self.ast = ast
        self.build_queue.append(ast)

        while True:
            script = self.build_queue.pop(0)
            cfg = CFG()
            self.cur_cfg = cfg
            self.cfgs.append(cfg)
            self.switchloop_stack = []
            self.try_stack = []
            self.prev_try_final_last_bb = None
            self.prev_logical_right_bb = None
            self.prev_logical_merge_bb = None
            # print(script.loc)

            cfg.script_id = script_id

            # get function offset
            if script.type in ['FunctionDeclaration', 'FunctionExpression'] and script.v8_offset is not None:
                fid = script.v8_offset
            else:
                fid = get_v8_offset(script)

            cfg.function_id = fid

            if script.id is not None:
                cfg.function_name = script.id.name

            # print(cfg.function_name, cfg.function_id)

            bb = self.new_bb(True)
            cfg.start_bb = bb

            if type(script.body) == list:
                self.visitStatementList(script.body)
            else:
                self.visit(script.body)

            cfg.cur_bb.control_type = CONTROL.End
            if len(cfg.cur_bb.successors) == 0:
                self.connect_bb(cfg.cur_bb, cfg.end_bb)

            cfg.end_bb.id = self.fetch_bb_newid(cfg)
            cfg.basic_blocks.append(cfg.end_bb)

            self.remove_empty_bb(cfg)
            self.remove_error_bb(cfg)

            if len(self.build_queue) == 0:
                break

        return self.cfgs

    def draw(self, cfg_indx, offset_mode=True):
        draw_cfg(self.cfgs[cfg_indx], offset_mode=offset_mode)

    def add_node_to_cur_bb(self, node, check_skip=True):
        if not check_skip or node.type not in NODE_TO_ADD_IN_VISIT \
                or (self.cur_bb().is_expression_block and node.type in ['Literal', 'Identifier', 'MemberExpression']):

            if node.v8_offset is not None:
                node.offset = node.v8_offset
            else:
                node.offset = get_v8_offset(node)
            self.cur_bb().statements.append(node)

    def add_to_build_queue(self, node):
        self.build_queue.append(node)

    def new_bb(self, change_cur=False, expression_block=False):
        cfg = self.cur_cfg
        bb = BasicBlock()
        bb.id = self.fetch_bb_newid(cfg)
        bb.is_expression_block = expression_block
        cfg.basic_blocks.append(bb)
        if change_cur:
            cfg.cur_bb = bb
        return bb

    def fetch_bb_newid(self, cfg):
        id = cfg.cur_bb_id
        cfg.cur_bb_id += 1
        return str(id)

    def connect_bb(self, bb1, bb2, loc=None):
        if loc is not None:
            bb1.successors.insert(loc, bb2)
        else:
            bb1.successors.append(bb2)
        bb2.predecessors.append(bb1)

    def disconnect_bb(self, bb1, bb2):
        bb1.successors.remove(bb2)
        bb2.predecessors.remove(bb1)

    def create_branch_and_visit(self, bb_control, bb_merge, visit_node, expression_branch=False):
        bb_branch = self.new_bb(True, expression_block=expression_branch)
        self.connect_bb(bb_control, bb_branch)
        self.visit(visit_node)
        bb_branch = self.cur_bb()

        if len(bb_branch.successors) == 0:
            self.connect_bb(bb_branch, bb_merge)

        return bb_branch

    def remove_empty_bb(self, cfg):
        bb_to_remove = []
        for bb in cfg.basic_blocks:
            if len(bb.statements) == 0:
                if len(bb.successors) > 1 or len(bb.successors) == 0: # error bb
                    continue

                succ = bb.successors[0]
                for pred in bb.predecessors:
                    pred.successors.remove(bb)
                    self.connect_bb(pred, succ)

                succ.predecessors.remove(bb)
                bb_to_remove.append(bb)

        for bb in bb_to_remove:
            cfg.basic_blocks.remove(bb)

    def remove_error_bb(self, cfg):
        # remove blocks have no predecessors except start block
        bb_to_remove = []
        for bb in cfg.basic_blocks[1:]:
            if len(bb.predecessors) == 0:
                bb_to_remove.append(bb)
                for succ in bb.successors:
                    succ.predecessors.remove(bb)

        for bb in bb_to_remove:
            cfg.basic_blocks.remove(bb)

    def cur_bb(self, new_bb=None):
        if new_bb is not None:
            self.cur_cfg.cur_bb = new_bb
        else:
            return self.cur_cfg.cur_bb

    # ================= visit functions ===================
    def visit(self, node):
        if node is None:
            return

        if node.type in NODE_TO_IGNORE:
            return

        # print('visit' + node.type)
        func = getattr(self, 'visit' + node.type)
        func(node)
        # try:
        #     func = getattr(self, 'visit' + node.type)
        #     func(node)
        # except AttributeError:
        #     print('visit' + node.type + ' - Not available or Error happened')
        #     print(node)
        #     # exit()
        #     # pass




    def visitStatementList(self, stmt_list):
        for stmt in stmt_list:
            if stmt is None:
                continue
            self.add_node_to_cur_bb(stmt)
            self.visit(stmt)
            if stmt.type in ['BreakStatement', 'ReturnStatement', 'ThrowStatement']:
                break

    def visitNodes(self, nodes):
        self.visitStatementList(nodes)
        # for node in nodes:
        #     self.add_node_to_cur_bb(node)
        #     self.visit(node)

    def visitBlockStatement(self, node):
        self.visitStatementList(node.body)

    def visitExpressionStatement(self, node):
        self.visit(node.expression)
        self.add_node_to_cur_bb(node.expression)

    def visitFunctionDeclaration(self, node):
        self.add_to_build_queue(node)

    def visitFunctionExpression(self, node):
        self.visitFunctionDeclaration(node)

    def visitArrowFunctionExpression(self, node):
        self.visitFunctionDeclaration(node)

    def visitWithStatement(self, node):
        self.visit(node.object)
        self.visit(node.body)

    def visitDoWhileStatement(self, node):
        self.add_node_to_cur_bb(node, False)
        bb_dowhile = self.cur_bb()
        bb_merge = self.new_bb()

        node.merge_bb = bb_merge

        self.switchloop_stack.append(node)
        self.create_branch_and_visit(bb_dowhile, bb_merge, node.body)
        self.switchloop_stack.pop()
        self.visit(node.test)
        self.cur_bb(bb_merge)

    def handleLoopStatement(self, node):
        self.add_node_to_cur_bb(node, False)
        bb_while = self.cur_bb()
        bb_merge = self.new_bb()

        node.merge_bb = bb_merge
        self.switchloop_stack.append(node)
        self.create_branch_and_visit(bb_while, bb_merge, node.body)
        if self.handle_loop_condition:
            bb_while.control_type = CONTROL.LoopCondition
            self.connect_bb(bb_while, bb_merge)

        self.switchloop_stack.pop()

        return bb_merge

    def visitWhileStatement(self, node):
        self.visit(node.test)
        bb_merge = self.handleLoopStatement(node)
        self.cur_bb(bb_merge)

    def visitForStatement(self, node):
        self.visit(node.init)
        self.visit(node.test)

        bb_merge = self.handleLoopStatement(node)

        self.visit(node.update)

        self.cur_bb(bb_merge)

    def visitForInStatement(self, node):
        self.visit(node.left)
        self.visit(node.right)

        bb_merge = self.handleLoopStatement(node)

        self.cur_bb(bb_merge)

    def visitForOfStatement(self, node):
        self.visitForInStatement(node)
        # self.visit(node.left)
        # self.visit(node.right)
        # self.switchloop_stack.append(node)
        # self.visit(node.body)
        # self.switchloop_stack.pop()

    def visitAssignmentExpression(self, node):
        self.visit(node.right)
        self.visit(node.left)


    def visitYieldExpression(self, node):
        self.visit(node.argument)

    def visitAwaitExpression(self, node):
        self.visit(node.argument)


    def visitSpreadElement(self, node):
        self.visit(node.argument)

    def visitArrayPattern(self, node):
        self.visitNodes(node.elements)

    def visitAssignmentPattern(self, node):
        self.visit(node.left)
        self.visit(node.right)

    def visitObjectPattern(self, node):
        self.visitObjectExpression(node)

    def visitArrayExpression(self, node):
        self.visitNodes(node.elements)

    def visitObjectExpression(self, node):
        self.visitNodes(node.properties)

    def visitProperty(self, node):
        self.visit(node.key)
        self.visit(node.value)

    def visitTaggedTemplateExpression(self, node):
        self.visit(node.tag)
        self.visitNodes(node.quasi.expressions)

    def visitMemberExpression(self, node):
        self.visit(node.object)
        self.visit(node.properety)

    def visitCallExpression(self, node):
        self.visitNodes(node.arguments)
        self.visit(node.callee)

        if node.callee.type != 'Identifier':
            if node.callee.type == 'MemberExpression' and not node.callee.computed:
                # a.b();
                node.v8_offset = get_v8_offset(node.callee.property)
            else:
                # a[b]();
                node.v8_offset = node.call_parentheses_offset
        elif node.parentheses_callee: #(abc)()
            node.v8_offset = node.call_parentheses_offset





        self.add_node_to_cur_bb(node, False)

    def visitNewExpression(self, node):
        self.visitNodes(node.arguments)
        self.visit(node.callee)

    def visitUpdateExpression(self, node):
        self.visit(node.argument)

    def visitUnaryExpression(self, node):
        self.visit(node.argument)

    def visitBinaryExpression(self, node):
        self.visit(node.left)
        self.visit(node.right)

    def visitIfStatement(self, node):
        self.visit(node.test)
        self.add_node_to_cur_bb(node, False)

        bb_if = self.cur_bb()
        bb_if.control_type = CONTROL.If
        bb_merge = self.new_bb()

        # then
        self.create_branch_and_visit(bb_if, bb_merge, node.consequent)

        # else
        if node.alternate is not None:
            self.create_branch_and_visit(bb_if, bb_merge, node.alternate)
        else:
            self.connect_bb(bb_if, bb_merge)

        self.cur_bb(bb_merge)

    def visitLogicalExpression(self, node):
        # print(node)
        # operator: '||' | '&&';
        self.visit(node.left)
        bb_merge = None
        if node.operator == '&&':
            if node.left.has_logical_branch is not None:
                self.cur_bb(node.left.logical_cur_bb)
                bb_merge = node.left.logical_merge_bb

                node.has_logical_branch = True
                node.logical_cur_bb = node.left.logical_cur_bb
                node.logical_merge_bb = node.left.logical_merge_bb

            bb_left = self.cur_bb()

            # check if right contains call expression
            # if node.right.type in ['CallExpression', ]:
            if str(node.right).find('CallExpression') != -1:
                if bb_merge is None:
                    bb_merge = self.new_bb(False)

                bb_left.control_type = CONTROL.Logical
                self.add_node_to_cur_bb(node, False)

                if bb_merge in bb_left.successors:
                    self.disconnect_bb(bb_left, bb_merge)
                bb_right = self.create_branch_and_visit(bb_left, bb_merge, node.right)
                node.has_logical_branch = True
                node.logical_cur_bb = bb_right
                node.logical_merge_bb = bb_merge
                self.connect_bb(bb_left, bb_merge)

            else:
                self.visit(node.right)

            self.cur_bb(bb_merge)
        else:
            self.visit(node.right)






    def visitConditionalExpression(self, node):
        self.visit(node.test)
        self.add_node_to_cur_bb(node, False)

        bb_condition = self.cur_bb()
        bb_condition.control_type = CONTROL.Conditional
        bb_merge = self.new_bb()

        self.create_branch_and_visit(bb_condition, bb_merge, node.consequent, expression_branch=True)

        self.add_node_to_cur_bb(node.consequent)
        self.create_branch_and_visit(bb_condition, bb_merge, node.alternate, expression_branch=True)
        self.add_node_to_cur_bb(node.alternate)

        self.cur_bb(bb_merge)

    def visitSwitchStatement(self, node):
        #TODO

        self.visit(node.discriminant)
        bb_switch = self.cur_bb()
        bb_switch.control_type = CONTROL.Switch
        self.add_node_to_cur_bb(node, False)

        bb_merge = self.new_bb()

        # cases - create blocks first
        bb_cases = [self.new_bb() for x in node.cases]

        default_id = -1
        bb_prev_label = bb_switch
        for i in range(len(node.cases)):
            case = node.cases[i]
            bb_case = bb_cases[i]
            if case.test is None: # default case
                default_id = i
            else:
                bb_label = self.new_bb(True, expression_block=True)
                self.connect_bb(bb_switch, bb_label)
                self.add_node_to_cur_bb(case.test)
                self.visit(case.test)
                bb_label = self.cur_bb()
                self.connect_bb(bb_label, bb_case)
                bb_label.control_type = CONTROL.SwitchLabel

            self.cur_bb(bb_case)
            self.switchloop_stack.append(case)
            self.visitNodes(case.consequent)
            self.switchloop_stack.pop()
            bb_case = self.cur_bb()

            # handle break
            if len(bb_case.successors) == 0:
                if case.has_break or i+1 == len(bb_cases): # has break stmt or this is the last label
                    self.connect_bb(bb_case, bb_merge)
                else:
                    self.connect_bb(bb_case, bb_cases[i+1])

        # handle default case here so that it can be the last one
        if default_id != -1:
            self.connect_bb(bb_switch, bb_cases[default_id])
        else:
            self.connect_bb(bb_switch, bb_merge)
        
        self.cur_bb(bb_merge)

    def visitSequenceExpression(self, node):
        self.visitNodes(node.expressions)

    def visitBreakStatement(self, node):
        if node.label: # break with label
            for lb_stmt in self.label_list:
                if lb_stmt.label.name == node.label.name:
                    self.add_node_to_cur_bb(node, False)
                    bb = self.cur_bb()
                    for succ in bb.successors:
                        self.disconnect_bb(bb, succ)

                    self.connect_bb(bb, lb_stmt.merge_bb)
                    bb.control_type = CONTROL.Break
                    break

        else:
            if len(self.switchloop_stack) == 0:
                return

            target_node = self.switchloop_stack[-1]
            self.add_node_to_cur_bb(node, False)

            if target_node.type != 'SwitchCase':
                bb = self.cur_bb()
                for succ in bb.successors:
                    self.disconnect_bb(bb, succ)

                self.connect_bb(bb, target_node.merge_bb)
                bb.control_type = CONTROL.Break
            else:
                target_node.has_break = True
                node.target_node = target_node


    def visitContinueStatement(self, node):
        # target_node = self.switchloop_stack[-1]
        # node.target_node = target_node
        # consider it as a break for this project
        self.visitBreakStatement(node)
    

    def visitClassDeclaration(self, node):
        self.visitClassExpression(node)

    def visitClassExpression(self, node):
        self.visitNodes(node.body.body)

    def visitMethodDefinition(self, node):
        self.visit(node.value)

    def visitLabeledStatement(self, node):
        self.add_node_to_cur_bb(node, False)
        bb_label = self.cur_bb()
        bb_label.control_type = CONTROL.Label
        bb_merge = self.new_bb()

        node.merge_bb = bb_merge
        self.label_list.append(node)
        self.visit(node.body)
        self.label_list.remove(node)

        bb = self.cur_bb()
        self.connect_bb(bb, bb_merge)

        self.cur_bb(bb_merge)


    def visitReturnStatement(self, node):
        self.visit(node.argument)
        self.add_node_to_cur_bb(node, False)
        bb = self.cur_bb()

        # remove all successors
        for succ in bb.successors:
            self.disconnect_bb(bb, succ)

        bb.control_type = CONTROL.Return

        # handle return in try block
        found_finally = False
        if len(self.try_stack) != 0:
            # check if any has final block
            return_chain_mode = False
            for i in range(len(self.try_stack)-1, -1, -1):
                try_node = self.try_stack[i]
                if try_node.finalizer is not None:
                    found_finally = True
                    if not return_chain_mode:
                        self.connect_bb(bb, try_node.finalizer.start_bb)
                        bb.control_type = CONTROL.ReturnToFinally
                        return_chain_mode = True
                    else:
                        try_node.finalizer.do_return_chain = True
                    if i == 0:
                        try_node.finalizer.may_return = True

        if not found_finally: # no finally, or just normal case
            self.connect_bb(bb, self.cur_cfg.end_bb)




    def visitThrowStatement(self, node):
        self.visit(node.argument)
        self.add_node_to_cur_bb(node, False)
        bb = self.cur_bb()
        bb.control_type = CONTROL.Throw

        # remove all successors
        for succ in bb.successors:
            self.disconnect_bb(bb, succ)

        if len(self.try_stack) != 0:
            found_catch = False
            final_node_to_be_connected = None
            try_node = None
            for i in range(len(self.try_stack)-1, -1, -1):
                try_node = self.try_stack[i]
                if try_node.handler is not None and try_node.current_block != 'catch': # Found the first catch
                    found_catch = True
                    if final_node_to_be_connected is not None:
                        final_node_to_be_connected.bb_to_pass_throw = try_node.handler.start_bb
                    else:
                        self.connect_bb(bb, try_node.handler.start_bb)
                    break

                else: # no catch in this try block or in a catch block
                    if try_node.finalizer is not None:
                        if final_node_to_be_connected is None: # first connect to finally
                            self.connect_bb(bb, try_node.finalizer.start_bb, 0)
                        else:
                            final_node_to_be_connected.bb_to_pass_throw = try_node.finalizer.start_bb

                        final_node_to_be_connected = try_node.finalizer

            if not found_catch and try_node.finalizer is not None:
                try_node.finalizer.may_return = True

        else:
            # no throw catcher
            self.connect_bb(bb, self.cur_cfg.end_bb)

    def visitTryStatement(self, node):
        self.add_node_to_cur_bb(node, False)
        bb_try = self.cur_bb()
        bb_try.control_type = CONTROL.Try

        # finally or just merge block
        bb_merge = self.new_bb()

        if node.handler is not None:
            bb_catch = self.new_bb()
            node.handler.start_bb = bb_catch

        if node.finalizer is not None:
            node.finalizer.start_bb = bb_merge
            node.finalizer.do_return_chain = False

        self.try_stack.append(node)
        node.current_block = 'try'
        # try block
        bb_try_block = self.new_bb(True)
        self.connect_bb(bb_try, bb_try_block)
        self.visit(node.block)
        bb_try_block = self.cur_bb()
        
        if len(bb_try_block.successors) == 0:
            self.connect_bb(bb_try_block, bb_merge)

        if node.handler is not None:
            node.current_block = 'catch'
            self.cur_bb(bb_catch)
            self.connect_bb(bb_try, bb_catch)
            self.visit(node.handler.body)
            bb_catch = self.cur_bb()

            if len(bb_catch.successors) == 0:
                self.connect_bb(bb_catch, bb_merge)

        self.try_stack.pop()
        
        self.cur_bb(bb_merge)
        bb_next = self.new_bb(False)
        if node.finalizer is not None:
            node.current_block = 'finally'
            self.visit(node.finalizer)
            bb_merge = self.cur_bb()

            if node.finalizer.do_return_chain:
                self.connect_bb(self.prev_try_final_last_bb, bb_merge, 0)
                self.prev_try_final_last_bb.control_type = CONTROL.MayReturnToFinally

            if node.finalizer.may_return:
                self.connect_bb(bb_merge, self.cur_cfg.end_bb)
                bb_merge.control_type = CONTROL.MayReturn

            if bb_merge.control_type not in [CONTROL.Return, CONTROL.Throw]:
                self.connect_bb(bb_merge, bb_next)
                if node.finalizer.bb_to_pass_throw:
                    self.connect_bb(bb_merge, node.finalizer.bb_to_pass_throw, 0)
                    bb_merge.control_type = CONTROL.ThrowChain

            self.prev_try_final_last_bb = bb_merge
        else:
            self.connect_bb(bb_merge, bb_next)

        node.current_block = None
        self.cur_bb(bb_next)
        
        
        
    def visitVariableDeclaration(self, node):
        self.visitNodes(node.declarations)

    def visitVariableDeclarator(self, node):
        self.visit(node.init)
        self.visit(node.id)
        self.add_node_to_cur_bb(node, False)

