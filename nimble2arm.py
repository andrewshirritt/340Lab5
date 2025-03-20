"""
Given a global scope and type annotations, and operating as an ANTLR
listener over a semantically-correct Nimble parse tree, generates equivalent
arm assembly code. Does not consider function definitions, function calls,
or return statements.

Authors: TODO: Your names here
Date: TODO: Submission date here

Instructor version: 2023-03-15
                    2025-02-13 Arm Update
"""

import templates
from nimble import NimbleListener, NimbleParser
from semantics import PrimitiveType


class ArmGenerator(NimbleListener):

    def __init__(self, global_scope, types, arm):
        self.current_scope = global_scope
        self.types = types
        self.arm = arm
        self.label_index = -1
        self.string_literals = {}


    def unique_label(self, base):
        """
        Given a base string "whatever", returns a string of the form "whatever_x",
        where the x is a unique integer. Useful for generating unique labels.
        """
        self.label_index += 1
        return f'{base}_{self.label_index}'

    # ---------------------------------------------------------------------------------
    # Provided for you
    # ---------------------------------------------------------------------------------

    def enterMain(self, ctx: NimbleParser.MainContext):
        self.current_scope = self.current_scope.child_scope_named('$main')


    def exitScript(self, ctx: NimbleParser.ScriptContext):
        self.arm[ctx] = templates.script.format(
            string_literals='\n'.join(f'{label}: .asciz {string}'
                                      for label, string in self.string_literals.items()),
            main=self.arm[ctx.main()]
        )

    def exitMain(self, ctx: NimbleParser.MainContext):
        self.arm[ctx] = "mov fp, sp\n" + self.arm[ctx.body()]
        self.current_scope = self.current_scope.enclosing_scope

    def exitBlock(self, ctx: NimbleParser.BlockContext):
        self.arm[ctx] = '\n'.join(self.arm[s] for s in ctx.statement())

    def exitBoolLiteral(self, ctx: NimbleParser.BoolLiteralContext):
        value = 1 if ctx.BOOL().getText() == 'true' else 0
        self.arm[ctx] = 'mov r0, {}\n'.format(value)

    def exitIntLiteral(self, ctx: NimbleParser.IntLiteralContext):
        self.arm[ctx] = 'mov r0, {}\n'.format(ctx.INT().getText())

    def exitStringLiteral(self, ctx: NimbleParser.StringLiteralContext):
        label = self.unique_label('string')
        self.string_literals[label] = ctx.getText()
        self.arm[ctx] = 'ldr r0, ={}\n'.format(label)

    def exitPrint(self, ctx: NimbleParser.PrintContext):
        """
        Bool values have to be handled separately, because we print 'true' or 'false'
        but the values are encoded as 1 or 0
        """
        if self.types[ctx.expr()] == PrimitiveType.Bool:
            self.arm[ctx] = templates.print_bool.format(expr=self.arm[ctx.expr()])
        else:
            # in the print syscall, 1 is the service code for Int, 0 for String
            self.arm[ctx] = templates.print_int_or_string.format(
                expr=self.arm[ctx.expr()],
                service_code=1 if self.types[ctx.expr()] == PrimitiveType.Int else 0
            )

    # ---------------------------------------------------------------------------------
    # Partially provided for you - see lab instructions for suggested order
    # ---------------------------------------------------------------------------------

    def exitBody(self, ctx: NimbleParser.BodyContext):
        temp = self.arm[ctx.varBlock()]
        temp += self.arm[ctx.block()]
        self.arm[ctx] = temp

    def exitAddSub(self, ctx: NimbleParser.AddSubContext):
        if self.types[ctx.expr(0)] == PrimitiveType.Int:
            self.arm[ctx] = templates.add_sub.format(
                operation='add' if ctx.op.text == '+' else 'sub',
                expr0=self.arm[ctx.expr(0)],
                expr1=self.arm[ctx.expr(1)]
            )
        else:
            self.arm[ctx] = templates.cat.format(
                expr0=self.arm[ctx.expr(0)],
                expr1=self.arm[ctx.expr(1)]
            )

    def exitIf(self, ctx: NimbleParser.IfContext):
        if not ctx.block(1):
            command = templates.if_.format(
                condition=self.arm[ctx.expr()],
                true_block=self.arm[ctx.block(0)],
                endif_label=self.unique_label('endif')
            )
        else:
            command = templates.if_else.format(
                condition=self.arm[ctx.expr()],
                true_block=self.arm[ctx.block(0)],
                false_block=self.arm[ctx.block(1)],
                true_label = self.unique_label('true'),
                false_label = self.unique_label('false'),
                endif_label=self.unique_label('endif')
            )
        self.arm[ctx] = command

    # ---------------------------------------------------------------------------------
    # Yours to implement - see lab instructions for suggested order
    # ---------------------------------------------------------------------------------

    def exitVarBlock(self, ctx: NimbleParser.VarBlockContext):
        list = []
        for var in ctx.varDec():
            list.append(self.arm[var])
        self.arm[ctx] = "\n".join(list)

    def exitVarDec(self, ctx: NimbleParser.VarDecContext):
        if ctx.expr():  #if vardec has an assignment
            expression = self.arm[ctx.expr()]
            self.arm[ctx] = expression + f"str r0, [sp, #-4]!\n"
        else:
            self.arm[ctx] =  f"\nstr r0, [sp, #-4]!\n"

    def exitAssignment(self, ctx: NimbleParser.AssignmentContext):
        #go to var index on stack
        symbol = self.current_scope.resolve_locally(ctx.ID().getText())
        frame_pointer_offset = 4 * (-1 * (symbol.index+1))
        expression = self.arm[ctx.expr()]
        #change it based on what is in
        command = expression + f"str r0, [fp, #{frame_pointer_offset}]\n"
        self.arm[ctx] = command

    #'while' expr '{' block '}'
    def exitWhile(self, ctx: NimbleParser.WhileContext):
        whileLabel=self.unique_label("while")
        endLabel=self.unique_label("while")
        continue_me = self.arm[ctx.expr()]
        block_statement = self.arm[ctx.block()]


        command = f"{whileLabel}:\n" + continue_me + (f"\ncbz r0, {endLabel}\n"
                                 f"{block_statement}\n"
                                 f"b {whileLabel}\n"
                                 f"{endLabel}:\n")
        self.arm[ctx] = command

    def exitNeg(self, ctx: NimbleParser.NegContext):
        if ctx.op.text == '!':

            self.arm[ctx] = self.arm[ctx.expr()]+"EOR r0, r0, 0b1\n"
        else:

            self.arm[ctx] = self.arm[ctx.expr()]+"mov r1, #0\nsub r0,r1,r0\n"

    # Rolls up an expression contained inside parentheses #
    def exitParens(self, ctx: NimbleParser.ParensContext):
        self.arm[ctx] = self.arm[ctx.expr()]

    def exitCompare(self, ctx: NimbleParser.CompareContext):

        trueLabel=self.unique_label('true')
        falseLabel=self.unique_label('false')
        endLabel=self.unique_label('end')

        #if it's a variable, the variable node will have put it in r0

        temp=self.arm[ctx.expr(0)]
        temp+="str r0, [sp, #-4]!\n"

        temp+=self.arm[ctx.expr(1)]
        temp+="str r0, [sp, #-4]!\n"
        temp+="ldr r0, [sp], 4\n"
        temp+="ldr r1, [sp], 4\n"

        if ctx.op.text == '<':
            temp+=f"CMP r1, r0\n"
            temp+=f"BLT {trueLabel}\n"
            temp+=f"B {falseLabel}\n"

        if ctx.op.text == '<=':
            temp += f"cmp r1, r0 \n"
            temp+=f"BLE {trueLabel}\n"
            temp+=f"B {falseLabel}\n"

        if ctx.op.text == '==':
            temp += f"cmp r1, r0 \n"
            temp+=f"BEQ {trueLabel}\n"
            temp+=f"B {falseLabel}\n"

        temp+=f"{falseLabel}: \n"
        temp+="MOV r0, #0\n"
        temp+=f"B {endLabel}\n"

        temp+=f"{trueLabel}: \n"
        temp+="MOV r0, #1\n"
        temp+=f"B {endLabel}\n"

        temp+=f"{endLabel}:\n"

        self.arm[ctx]=temp


    def exitVariable(self, ctx: NimbleParser.VariableContext):
        # Loads a value into r0 based on the variable offset from the
        # frame pointer#
        symbol = self.current_scope.resolve_locally(ctx.ID().getText())
        if symbol.is_param:
            frame_pointer_offset = (-1 * (symbol.index+1))
        else:
            frame_pointer_offset = symbol.index + 1
        offset = frame_pointer_offset * -4
        command = f'ldr r0, [fp, #{offset}]\n'

        self.arm[ctx] = command

    def exitMulDiv(self, ctx: NimbleParser.MulDivContext):
        self.arm[ctx] = templates.add_sub.format(
            operation='MUL' if ctx.op.text == '*' else 'SDIV',
            expr0=self.arm[ctx.expr(0)],
            expr1=self.arm[ctx.expr(1)])