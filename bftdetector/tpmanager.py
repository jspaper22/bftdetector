from .jscfg.types import CONTROL


class ModType:
    NoMod = '0'
    Disable = '1'
    ForcedExecution = '2'


class TamperingProposal:
    def __init__(self, sid='', stmt_pos='', branch='', mod_type=ModType.NoMod, opt='0'):
        self.sid = sid
        self.stmt_pos = stmt_pos
        self.branch = branch
        self.mod_type = mod_type
        self.opt = opt

    def to_string(self):
        return ':'.join([self.stmt_pos, self.branch, self.mod_type, self.opt])
        # return ':'.join([self.sid, self.stmt_pos, self.branch, self.mod_type, self.opt])


class TPManager:
    @staticmethod
    def generate_tp(jscfg, data):
        caller_info = data['caller']
        sid = caller_info['sid']
        cfg_indx, cfg = jscfg.find_cfg(caller_info['pos'])

        tp = TPManager.generate_tp_b_side(jscfg, sid, data['call_pos_b'], cfg_indx, cfg)
        tp_a = TPManager.generate_tp_a_side(jscfg, sid, data['call_pos_a'], cfg_indx, cfg)

        tp['all'] += tp_a

        return tp

    @staticmethod
    def generate_tp_a_side(jscfg, sid, call_pos_list, cfg_indx, cfg):
        tp_list = []
        for call_pos in call_pos_list:
            bb = jscfg.find_stmt(cfg_indx, call_pos)
            if bb is None:
                # print('Failed to find stmt:', call_pos)
                continue
            # get cd
            try:
                cd_bb_ids = jscfg.get_cd(cfg_indx, bb.id)
            except:
                #print('Getting CD Error')
                cd_bb_ids = []

            tp_for_this_call = []

            for cd_bb_id in cd_bb_ids:
                cd_bb = jscfg.cfgs[cfg_indx].get_bb_by_id(cd_bb_id)
                # ignore logical??
                if cd_bb.control_type == CONTROL.Logical:
                    continue

                # ignore if this is try-catch
                if cd_bb.control_type in [CONTROL.Try, CONTROL.ReturnToFinally
                    , CONTROL.ThrowChain, CONTROL.MayReturnToFinally, CONTROL.MayReturn]:
                    continue

                branch_indx = cfg.get_connected_edge(cd_bb.id, bb.id)
                if branch_indx is None:
                    #print('Failed to getting connected branch index between', cd_bb.id, bb.id)
                    continue

                stmt_pos = str(cd_bb.statements[-1].offset)

                tp = TamperingProposal(sid, stmt_pos, str(branch_indx), ModType.ForcedExecution)
                tp_for_this_call.append(tp.to_string())
            if len(tp_for_this_call) != 0:
                tp_list.append(','.join(tp_for_this_call))

        # remove dup without ruining order.
        seen = set()
        seen_add = seen.add
        tp_list = [x for x in tp_list if not (x in seen or seen_add(x))]

        return tp_list

    @staticmethod
    def generate_tp_b_side(jscfg, sid, call_pos_list, cfg_indx, cfg):
        tp_list = []
        tp_call_dis_only_list = []
        for call_pos in call_pos_list:
            # 1. disable callee
            tp = TamperingProposal(sid, call_pos, '0', ModType.Disable)
            tp_list.append(tp.to_string())

            tp_call_dis_only_list.append(TamperingProposal(sid, call_pos, '0', ModType.Disable).to_string())

            bb = jscfg.find_stmt(cfg_indx, call_pos)
            if bb is None:
                # print('Failed to find stmt:', call_pos)
                continue
            # get cd
            try:
                cd_bb_ids = jscfg.get_cd(cfg_indx, bb.id)
            except:
                #print('Getting CD Error')
                cd_bb_ids = []

            for cd_bb_id in cd_bb_ids:
                cd_bb = jscfg.cfgs[cfg_indx].get_bb_by_id(cd_bb_id)
                # ignore if this is try-catch
                if cd_bb.control_type in [CONTROL.Try, CONTROL.ReturnToFinally
                    , CONTROL.ThrowChain, CONTROL.MayReturnToFinally, CONTROL.MayReturn]:
                    continue

                branch_indx = cfg.get_connected_edge(cd_bb.id, bb.id)
                if branch_indx is None:
                    #print('Failed to getting connected branch index between', cd_bb.id, bb.id)
                    continue

                stmt_pos = str(cd_bb.statements[-1].offset)

                # 2. disable block
                tp = TamperingProposal(sid, stmt_pos, str(branch_indx), ModType.Disable)
                tp_list.append(tp.to_string())

                if cd_bb.control_type == CONTROL.Logical:
                    continue

                # 3. forced execution
                for indx, branch_id in enumerate(cfg.nx_graph[cd_bb.id]):
                    if indx == branch_indx:
                        continue

                    tp = TamperingProposal(sid, stmt_pos, str(indx), ModType.ForcedExecution)
                    tp_list.append(tp.to_string())

        # remove dup without ruining order.
        seen = set()
        seen_add = seen.add
        tp_list = [x for x in tp_list if not (x in seen or seen_add(x))]

        return {'all': tp_list,
                'call_dis_only': tp_call_dis_only_list}
