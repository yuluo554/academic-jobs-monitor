"""HTML 条目定位：标准库解析层的公共轻量工具。

只做"HTML → 节点流"的结构化读取（事件序列 + 简易 DOM 树），不承载任何
站点特定的解析假设（K5：逐源规则在各适配器内）；无启发式兜底。
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass, field
from html.parser import HTMLParser


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node(tag="#root")
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag=tag, attrs={k: v or "" for k, v in attrs})
        self._stack[-1].children.append(node)
        # void 元素不入栈（HTML5 语义，html.parser 不会为它们补 close 事件）
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        # 容错回退：malformed HTML 下同名标签未闭合时退到最近同名祖先再弹出。
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag=tag, attrs={k: v or "" for k, v in attrs})
        self._stack[-1].children.append(node)

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source"}
)


@dataclass(slots=True)
class Node:
    """轻量 DOM 节点；children 混装 Node 与 str（文本）。"""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)

    def iter(self):
        """深度优先遍历全部后代节点（不含自身）。"""
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag: str, *, class_contains: str | None = None) -> list[Node]:
        """按标签名（可选 class 含子串）筛选后代，文档序。"""
        out = []
        for node in self.iter():
            if node.tag != tag:
                continue
            if class_contains is not None and class_contains not in node.attrs.get("class", ""):
                continue
            out.append(node)
        return out

    def find(
        self, tag: str, *, class_contains: str | None = None, attr: str | None = None,
        attr_contains: str | None = None,
    ) -> Node | None:
        for node in self.iter():
            if node.tag != tag:
                continue
            if class_contains is not None and class_contains not in node.attrs.get("class", ""):
                continue
            if attr is not None and attr not in node.attrs:
                continue
            if attr_contains is not None and attr_contains not in node.attrs.get(attr or "", ""):
                continue
            return node
        return None

    def text(self) -> str:
        """直接文本内容（含后代文本，标签不展开属性），空白折叠交给调用方。"""
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(child.text())
        return _html.unescape("".join(parts))


def parse_html(body: str) -> Node:
    """解析 HTML 为轻量节点树。malformed 输入不抛异常（html.parser 容错语义）。"""
    builder = _TreeBuilder()
    builder.feed(body)
    builder.close()
    return builder.root
