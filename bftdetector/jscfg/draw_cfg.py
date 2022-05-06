import json
from graphviz import Digraph
from .types import BasicBlock, CFG, CONTROL


def draw_cfg(cfg, bb_ids=None, cds=None, offset_mode=True, output_path=None):
    # print('function id : ', cfg.function_id)

    filename = 'output.gv'
    if output_path:
        filename = output_path + '/' + str(cfg.function_id) + '.gv'

    g = Digraph('G', filename=filename, node_attr={'shape': 'plaintext'})

    for bb in cfg.basic_blocks[:-1]:
        id = bb.id
        highlight = ''

        if bb_ids is not None or cds is not None:
            if id in bb_ids:
                highlight = 'BGCOLOR="yellow"'
            elif id in cds:
                highlight = 'BGCOLOR="green"'

        # if bb_id is None:
        #     for call in data['trace_calls']:
        #         if id == call['id']:
        #             highlight = 'BGCOLOR="yellow"'
        #             break
        # else:
        #     if id == sbb_id:
        #         highlight = 'BGCOLOR="yellow"'
        #     elif id in cds:
        #         highlight = 'BGCOLOR="green"'

        # node
        stmt_str = ''
        for stmt in bb.statements:

            #node_type = NODETYPE[int(stmt['node_type'])]
            node_type = stmt.type
            if offset_mode:
                # line = str(stmt.range[0])
                line = str(stmt.offset)
            else:
                line = str(stmt.loc.start.line) + ':' + str(stmt.loc.start.column + 1)
            line += "\t " + node_type

            # if highlight != '':
            #     for call in data['trace_calls']:
            #         if stmt['position'] == call['pos']:
            #             str = '<B>' + str + '</B>'
            #             break

            stmt_str += line + '<br/>'

        node_html = '''<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
            <tr>
                <td port="id" %s>%s</td>
            </tr>
            <tr>
                <TD port="data" BALIGN="LEFT">%s</TD>
            </tr>
        </TABLE>
        >'''%(highlight, id, stmt_str)

        g.node(id, node_html)

        # edge
        if bb.control_type == CONTROL.Return:
            g.edge(id + ':data', bb.successors[0].id + ":id", constraint='true', label='return', style='dashed')
        if bb.control_type == CONTROL.ReturnToFinally:
            g.edge(id + ':data', bb.successors[0].id + ":id", constraint='true', label='return-to-finally', style='dashed')
        elif bb.control_type == CONTROL.Throw:
            g.edge(id + ':data', bb.successors[0].id + ":id", constraint='true', label='throw', style='dashed')
        elif bb.control_type == CONTROL.Break:
            g.edge(id + ':data', bb.successors[0].id + ":id", label='break', style='dashed')
        elif bb.control_type in [CONTROL.If, CONTROL.Conditional, CONTROL.LoopCondition, CONTROL.Logical]:
            g.edge(id + ':data', bb.successors[0].id + ":id", label='T')
            g.edge(id + ':data', bb.successors[1].id + ":id", label='F')
        elif bb.control_type == CONTROL.Try:
            g.edge(id + ':data', bb.successors[0].id + ":id")
            if len(bb.successors) > 1:
                g.edge(id + ':data', bb.successors[1].id + ":id", label='catch', style='dotted')
        elif bb.control_type == CONTROL.MayReturnToFinally:
            g.edge(id + ':data', bb.successors[0].id + ":id", constraint='true', label='may-return-to-finally', style='dotted')
            for succ in bb.successors[1:]:
                g.edge(id + ':data', succ.id + ":id")

        elif bb.control_type == CONTROL.MayReturn:
            g.edge(id + ':data', bb.successors[0].id + ":id", constraint='true', label='may-return', style='dotted')
            for succ in bb.successors[1:]:
                g.edge(id + ':data', succ.id + ":id")

        elif bb.control_type == CONTROL.ThrowChain:
            g.edge(id + ':data', bb.successors[0].id + ":id", constraint='true', label='throw-chain', style='dotted')
            for succ in bb.successors[1:]:
                g.edge(id + ':data', succ.id + ":id")

        elif bb.control_type == CONTROL.Switch:
            for succ in bb.successors[:-1]:
                g.edge(id + ':data', succ.id + ":id")
            g.edge(id + ':data', bb.successors[-1].id + ":id", label='Default')
        else:
            for succ in bb.successors:
                g.edge(id + ':data', succ.id + ":id")

    # end node
    lastid = cfg.basic_blocks[-1].id
    g.node(lastid, 'END', shape='circle')

    for i, line in enumerate(g.body):
        if lastid + ':id' in line:
            g.body[i] = line.replace(lastid + ':id', lastid)

    g.body.append('labelloc="t";label="[' + cfg.function_name + '](' + str(cfg.script_id) + ':' + str(cfg.function_id) + ')  ";')
    g.view()