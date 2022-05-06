from bs4 import BeautifulSoup


class DomDiff:
    def __init__(self):
        pass

    def prettify(self, bs, remove_head_and_script = True):
        # ads = ['.GoogleDfpAd-wrapper']
        # ads = ['div.ad']
        # for ad in ads:
        #     for tag in bs.select(ad):
        #         tag.decompose()

        # if remove_head_and_script:
        #     if bs.head:
        #         bs.head.decompose()
        #     for tag in bs.find_all('script'):
        #         tag.decompose()

        # to_remove = ['head','script','iframe','span','img','video','a']
        to_remove = ['head', 'script']
        for tag in to_remove:
            for remove in bs.find_all(tag):
                remove.decompose()

        return str(bs.prettify()).split('\n')

    def extract_tags(self, html_lines, div_only):
        output = []

        for line in html_lines:
            pos = line.find('<')
            if pos == -1:
                continue

            if div_only is False:
                if line[pos:pos + 2] != '</':
                    output.append(line[pos:])
            else:
                pos2 = line.find('<div')
                if pos2 != -1:
                    output.append(line[pos2:])

        return output

    #
    # def extract_div_only(self, bs):
    #     for tag in bs.find_all('div'):
    #

    def extract_tags_from_file(self, filename, remove_head_and_script=True, div_only=True):
        with open(filename, 'r') as f:
            bs = BeautifulSoup(f, 'html.parser')

        html_lines = self.prettify(bs, remove_head_and_script)

        return self.extract_tags(html_lines, div_only)


    def load_files(self, filenames, div_only=True):
        tag_sets = []
        for filename in filenames:
            tag_sets.append(set(self.extract_tags_from_file(filename, div_only=div_only)))

        union = tag_sets[0].copy()
        intersection = tag_sets[0].copy()
        if len(tag_sets) > 1:
            for tag_set in tag_sets[1:]:
                union |= tag_set
                intersection &= tag_set

        return union, intersection

    def getDomDiff(self, files_a, files_b, div_only=True):
        final_set_a, final_set_b, common = self.getDomDiffWithCommon(files_a, files_b, div_only)
        return final_set_a, final_set_b

    def getDomDiffWithCommon(self, files_a, files_b, div_only=True):
        a_uni, a_inter = self.load_files(files_a, div_only)
        b_uni, b_inter = self.load_files(files_b, div_only)

        final_set_a = a_inter - b_uni
        final_set_b = b_inter - a_uni

        common = a_inter & b_inter

        return final_set_a, final_set_b, common


    def loadSelectorsFromFiles(self, filenames, div_only):
        selectors_list = []
        for filename in filenames:
            tags = self.extract_tags_from_file(filename, div_only=div_only)
            selectors = set(self.getSelectors(tags))
            selectors_list.append(selectors)

        union = selectors_list[0].copy()
        intersection = selectors_list[0].copy()
        if len(selectors_list) > 1:
            for tag_set in selectors_list[1:]:
                union |= tag_set
                intersection &= tag_set

        return union, intersection

    def getSelectorDiffwithCommon(self, files_a, files_b, div_only=True):
        a_uni, a_inter = self.loadSelectorsFromFiles(files_a, div_only)
        b_uni, b_inter = self.loadSelectorsFromFiles(files_b, div_only)

        final_set_a = a_inter - b_uni
        final_set_b = b_inter - a_uni

        common = a_inter & b_inter

        return final_set_a, final_set_b, common


    def getSelectors(self, html_lines, fine_mode=True):
        selectors = []
        for line in html_lines:
            bs = BeautifulSoup(line, 'html.parser')
            tag = None
            for content in bs.contents:
                if content.name is not None:
                    tag = content
                    break

            selector = []

            if tag is not None:
                if 'id' in tag.attrs and tag['id'] != '':
                    selector.append('#' + tag['id'])
                if 'class' in tag.attrs and len(tag['class']) != 0:
                    selector.append(tag.name + ''.join(['.' + x for x in tag['class']]))

                if not fine_mode and len(selector) > 2:
                    selector = [selector[1]]

            selectors += selector

        return set(selectors)
