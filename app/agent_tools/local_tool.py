from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar, cast

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


class LocalToolBinding(Generic[ModelT]):
    """本地工具绑定。

    它模拟 LangChain StructuredTool 的核心契约：name、description、args_schema
    和 invoke。这样即使当前环境还没安装 langchain_core，也能先完成工具注册、
    测试和 MockRuntime 接入。安装依赖后，to_langchain_tool() 可转换为真实工具。
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        args_schema: type[ModelT],
        func: Callable[[ModelT], Any],
    ) -> None:
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self.func = func

    def invoke(self, args: dict[str, Any] | BaseModel) -> Any:
        """按 schema 校验输入并执行工具。"""

        payload = cast(ModelT, args) if isinstance(args, self.args_schema) else self.args_schema.model_validate(args)
        return self.func(payload)

    def run(self, args: dict[str, Any] | BaseModel) -> Any:
        """兼容常见 tool.run 调用习惯。"""

        return self.invoke(args)

    def to_langchain_tool(self) -> Any:
        """转换为 LangChain StructuredTool。

        当前环境没有安装 langchain_core 时会抛出清晰异常。后续真实 LangGraph
        runtime 可以在依赖安装后调用这个方法。
        """

        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise RuntimeError("缺少 langchain_core，无法转换为 StructuredTool。") from exc

        def _wrapped(**kwargs: Any) -> Any:
            return self.invoke(kwargs)

        return StructuredTool.from_function(
            func=_wrapped,
            name=self.name,
            description=self.description,
            args_schema=self.args_schema,
        )


def make_tool(
    *,
    name: str,
    description: str,
    args_schema: type[ModelT],
    func: Callable[[ModelT], Any],
) -> LocalToolBinding[ModelT]:
    """创建本地工具绑定。"""

    return LocalToolBinding(name=name, description=description, args_schema=args_schema, func=func)
