from . import equip_graph
from .jscfgbuilder import JSCFGBuilder
from .types import BasicBlock, CFG, CONTROL
from .draw_cfg import draw_cfg
from .equip_graph import DiGraph, DominatorTree, ControlDependence


class JSCFGManager:
    def __init__(self):
        self.cfgs = []
        self.script_info = {}

    def build_cfgs(self, code=None, filename=None, script_id=-1):
        # print('Buidling cfgs... [',script_id,']...', end='\t')
        builder = JSCFGBuilder()
        self.cfgs = builder.build(code, filename, script_id)

        self.script_info['filename'] = filename
        self.script_info['code'] = code
        self.script_info['script_id'] = script_id

        # print('Done')

        return self.cfgs

    def draw_cfg(self, cfg_indx, offset_mode=True, output_path=None):
        draw_cfg(self.cfgs[cfg_indx], offset_mode=offset_mode, output_path=output_path)

    def draw_with_cd(self, cfg_indx, bb_id, cds, offset_mode=True, output_path=None):
        draw_cfg(self.cfgs[cfg_indx], bb_id, cds, offset_mode=offset_mode, output_path=output_path)

    def find_cfg(self, function_id):
        if type(function_id) is str:
            function_id = int(function_id)

        for indx, cfg in enumerate(self.cfgs):
            if cfg.function_id == function_id:
                return indx, cfg

        return -1, None

    def find_cfg_by_name(self, func_name):
        for indx, cfg in enumerate(self.cfgs):
            if cfg.function_name == func_name:
                return indx, cfg

        return -1, None

    def find_stmt(self, cfg_indx, stmt_offset):
        if type(stmt_offset) is str:
            stmt_offset = int(stmt_offset)

        for bb in self.cfgs[cfg_indx].basic_blocks:
            for stmt in bb.statements:
                #if stmt.range[0] == stmt_offset:
                if stmt.offset == stmt_offset:
                    return bb

        return None

    def find_stmt_full(self, stmt_offset):
        cfg_cnt = len(self.cfgs)
        for i in range(cfg_cnt):
            bb = self.find_stmt(i, stmt_offset)
            if bb is not None:
                return i, bb

        return None, None


    def get_cd(self, cfg_indx, bb_id):
        cfg = self.cfgs[cfg_indx]

        if cfg.equip_cd_graph is None:
            self.__build_equip_graph(cfg)

        # find this node from cd graph
        nodes = list(cfg.equip_cd_graph.nodes)
        cur_node = None
        for node in nodes:
            if node.data == bb_id:
                cur_node = node
                break

        if cur_node is None:
            return []

        cd_nodes = []
        while True:
            in_edges = cfg.equip_cd_graph.in_edges(cur_node)
            if len(in_edges) == 0:
                break
            pred = in_edges[0].source
            cd_nodes.append(pred.data)
            cur_node = pred

        return cd_nodes

    def __get_dom_pdom(self, cfg_indx, bb_id, dom_type):
        cfg = self.cfgs[cfg_indx]

        if cfg.equip_dom_tree is None:
            self.__build_equip_graph(cfg)

        if dom_type == 'dom':
            tree_data = cfg.equip_dom_tree.dom
        else:
            tree_data = cfg.equip_dom_tree.post_dom

        # find this node from cd graph
        nodes = list(tree_data)
        cur_node = None
        for node in nodes:
            if node.data == bb_id:
                cur_node = node
                break

        if cur_node is None:
            return []

        dom_nodes = []
        while True:
            parent = tree_data.get(cur_node, None)
            if parent is None or parent == cur_node:
                break
            dom_nodes.append(parent.data)
            cur_node = parent

        return dom_nodes

    def get_doms(self, cfg_indx, bb_id):
        return self.__get_dom_pdom(cfg_indx, bb_id, 'dom')

    def get_pdoms(self, cfg_indx, bb_id):
        return self.__get_dom_pdom(cfg_indx, bb_id, 'pdom')

    def __build_equip_graph(self, cfg):
        g = DiGraph()
        nodes = {}
        node_list = []
        for bb in cfg.basic_blocks:
            node = g.make_add_node(data=bb.id)
            nodes[bb.id] = node
            node_list.append(node)

        for bb in cfg.basic_blocks:
            for succ in bb.successors:
                if succ:
                    g.make_add_edge(nodes[bb.id], nodes[succ.id])

        class EQUIP_CFG:
            graph = None
            entry_node = None
            exit_node = None
            dominators = None

        equip_cfg = EQUIP_CFG()
        equip_cfg.graph = g
        equip_cfg.entry_node = node_list[0]
        equip_cfg.exit_node = node_list[-1]
        equip_cfg.dominators = equip_graph.DominatorTree(equip_cfg)
        cfg.equip_dom_tree = equip_cfg.dominators
        cfg.equip_cd_graph = equip_graph.ControlDependence(equip_cfg).graph

    def get_bbs_to_track(self, cfg_indx, stmt_offset):
        if stmt_offset == -1:
            bb = self.cfgs[cfg_indx].end_bb
        else:
            bb = self.find_stmt(cfg_indx, stmt_offset)

        bb_list_to_track = []
        bb_queue = [bb]
        bb_queue_done = []

        while len(bb_queue) != 0:
            cur_bb = bb_queue.pop(0)
            doms = self.get_doms(cfg_indx, cur_bb.id)
            bb_list_to_track += [pred for pred in cur_bb.predecessors if pred.id not in doms]

            bb_queue_done.append(cur_bb)
            bb_queue += [pred for pred in cur_bb.predecessors if pred not in bb_queue + bb_queue_done]

        # # remove pdom nodes
        # total_pdoms = set()
        # for cur_bb in bb_list_to_track:
        #     total_pdoms |= set(self.get_pdoms(cfg_indx, cur_bb.id))
        #
        # # remove if my dom is in the track list
        # bb_to_remove = []
        # for cur_bb in bb_list_to_track:
        #     if cur_bb.id in total_pdoms:
        #         bb_to_remove.append(cur_bb)
        #
        # bb_list_to_track = list(set(bb_list_to_track) - set(bb_to_remove))


        # forcibly add start node
        if self.cfgs[cfg_indx].start_bb not in bb_list_to_track:
            bb_list_to_track.append(self.cfgs[cfg_indx].start_bb)

        # get the first stmts' offsets
        offsets = set()
        for bb_item in bb_list_to_track:
            for stmt in bb_item.statements:
                if stmt.type not in ['FunctionExpression', 'FunctionDeclaration']:
                    offsets.add(str(stmt.offset))
                    break

        # add call pos bb
        if stmt_offset != -1:
            offsets.add(str(stmt_offset))
            # if bb not in bb_list_to_track:
            #     bb_list_to_track.append(bb)


        # if len(offsets) == 0:
        #     bb = self.cfgs[cfg_indx].start_bb
        #     offsets.append(bb.statements[0].offset)



        return bb_list_to_track, list(offsets), bb

    def get_bbs_to_track_all(self, cfg_indx, stmt_offset):
        if stmt_offset == -1:
            bb = self.cfgs[cfg_indx].end_bb
        else:
            bb = self.find_stmt(cfg_indx, stmt_offset)

        if bb is None:
            print('Failed to find BB', cfg_indx, stmt_offset)
            return None, None, None

        bb_list_to_track = []
        bb_queue = [bb]
        bb_queue_done = []

        while len(bb_queue) != 0:
            cur_bb = bb_queue.pop(0)
            bb_list_to_track += cur_bb.predecessors

            bb_queue_done.append(cur_bb)
            bb_queue += [pred for pred in cur_bb.predecessors if pred not in bb_queue + bb_queue_done]

        # get the first stmts' offsets
        offsets = set()
        for bb_item in bb_list_to_track:
            for stmt in bb_item.statements:
                if stmt.type not in ['FunctionExpression', 'FunctionDeclaration']:
                    offsets.add(str(stmt.offset))
                    break

        # add call pos bb
        if stmt_offset != -1:
            offsets.add(str(stmt_offset))

        return bb_list_to_track, list(offsets), bb


    def get_bbs_to_track_cdonly(self, cfg_indx, stmt_offset):
        if stmt_offset == -1:
            bb = self.cfgs[cfg_indx].end_bb
        else:
            bb = self.find_stmt(cfg_indx, stmt_offset)

        cd_bb_ids = self.get_cd(cfg_indx, bb.id)
        if len(cd_bb_ids) < 2:
            return None, None, None

        bb_list_to_track = []
        for id in cd_bb_ids:
            bb_list_to_track.append(self.cfgs[cfg_indx].get_bb_by_id(id))

        # forcibly add start node
        # if self.cfgs[cfg_indx].start_bb not in bb_list_to_track:
        #     bb_list_to_track.append(self.cfgs[cfg_indx].start_bb)

        # get the first stmts' offsets
        offsets = set()
        for bb_item in bb_list_to_track:
            for stmt in bb_item.statements:
                if stmt.type not in ['FunctionExpression', 'FunctionDeclaration']:
                    offsets.add(str(stmt.offset))
                    break

        # add call pos bb
        if stmt_offset != -1:
            offsets.add(str(stmt_offset))
            # if bb not in bb_list_to_track:
            #     bb_list_to_track.append(bb)


        # if len(offsets) == 0:
        #     bb = self.cfgs[cfg_indx].start_bb
        #     offsets.append(bb.statements[0].offset)



        return bb_list_to_track, list(offsets), bb




    def reconst_path(self, cfg_indx, stmt_offset_list):

        path_bb_list = set()
        for stmt_offset in stmt_offset_list:
            bb = self.find_stmt(cfg_indx, stmt_offset)
            doms = self.get_doms(cfg_indx, bb.id)
            # pdoms = self.get_pdoms(cfg_indx, bb.id)
            path_bb_list.add(bb.id)
            # path_bb_list |= set(doms) | set(pdoms)
            path_bb_list |= set(doms)


        # arrange
        sorted_bb_list = []
        bb = self.cfgs[cfg_indx].start_bb
        sorted_bb_list.append(bb.id)

        while True:
            next_bb = None
            for succ in bb.successors:
                if succ.id in path_bb_list:
                    next_bb = succ
                    sorted_bb_list.append(succ.id)
                    break
            if next_bb is None:
                break
            bb = next_bb

        print(list(path_bb_list))
        print(sorted_bb_list)


        return sorted_bb_list







