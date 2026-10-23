import ast
import operator

from pydantic import BaseModel, Field


class Calculation(BaseModel):
    expression: str = Field(min_length=1, max_length=100)


class ToolRegistry:
    def __init__(self):
        self.tools = {"calculator": (Calculation, calculate)}

    def execute(self, name, arguments, allowed):
        if name not in allowed or name not in self.tools:
            raise ValueError("tool_not_allowed")
        schema, function = self.tools[name]
        return function(schema.model_validate(arguments))


def calculate(args):
    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            value = operations[type(node.op)](visit(node.left), visit(node.right))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        else:
            raise ValueError("unsupported_expression")
        if not -1e12 <= value <= 1e12:
            raise ValueError("calculation_out_of_range")
        return value

    return {"value": visit(ast.parse(args.expression, mode="eval").body)}
