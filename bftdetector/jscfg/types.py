from enum import Enum
import networkx as nx


class CONTROL(Enum):
    Null = 1
    If = 3
    Conditional = 4
    Switch = 5
    SwitchLabel = 6
    Try = 7
    ReturnToFinally = 8
    ThrowChain = 9
    End = 10
    Break = 11
    Return = 12
    Throw = 13
    LoopCondition = 14
    Logical = 15
    MayReturnToFinally = 16
    MayReturn = 17
    Label = 18


class BasicBlock:
    def __init__(self):
        self.id = ''
        self.statements = []
        self.predecessors = []
        self.successors = []
        self.control_stmt = None
        self.control_type = CONTROL.Null
        self.is_expression_block = False


class CFG:
    def __init__(self):
        self.function_id = -1
        self.script_id = -1
        # self.source_url = ''
        self.function_name = ''
        self.basic_blocks = []
        self.start_bb = None
        self.end_bb = BasicBlock()
        self.cur_bb = None
        self.cur_bb_id = 0
        self.nx_graph = None
        self.equip_cd_graph = None
        self.equip_dom_tree = None

    def get_bb_by_id(self, bb_id):
        for bb in self.basic_blocks:
            if bb.id == bb_id:
                return bb

        return None

    def get_connected_edge(self, start_id, end_id):
        if self.nx_graph is None:
            self.construct_nx_graph()

        for succ_id in self.nx_graph[start_id]:
            if nx.has_path(self.nx_graph, succ_id, end_id):
                return self.nx_graph[start_id][succ_id]['branch_index']

        return None

    def construct_nx_graph(self):
        self.nx_graph = nx.DiGraph()
        for bb in self.basic_blocks:
            self.nx_graph.add_node(bb.id)

            for i, succ in enumerate(bb.successors):
                self.nx_graph.add_edge(bb.id, succ.id)
                self.nx_graph[bb.id][succ.id]['branch_index'] = i

    # def get_id(self):
    #     return str(self.script_id) + '|' + str(self.function_id)
