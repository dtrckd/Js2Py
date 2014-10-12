
import types
import opcode

# Opcode constants used for comparison and replacecment
LOAD_FAST = opcode.opmap['LOAD_FAST']
LOAD_GLOBAL = opcode.opmap['LOAD_GLOBAL']
STORE_FAST = opcode.opmap['STORE_FAST']


def add_locals(func, locals_):
    keys = tuple(locals_.keys())
    vals = tuple(locals_[k] for k in keys)
    return types.FunctionType(append_arguments(func.func_code, keys), func.func_globals, argdefs=vals)

def append_arguments(code_obj, new_locals):
    co_varnames = code_obj.co_varnames   # Old locals
    co_names = code_obj.co_names      # Old globals
    co_argcount = code_obj.co_argcount     # Argument count
    co_code = code_obj.co_code         # The actual bytecode as a string

    # Make one pass over the bytecode to identify names that should be
    # left in code_obj.co_names.
    not_removed = set(opcode.hasname) - set([LOAD_GLOBAL])
    saved_names = set()
    for inst in instructions(co_code):
        if inst[0] in not_removed:
            saved_names.add(co_names[inst[1]])

    # Build co_names for the new code object. This should consist of
    # globals that were only accessed via LOAD_GLOBAL
    names = tuple(name for name in co_names
                  if name not in set(new_locals) - saved_names)

    # Build a dictionary that maps the indices of the entries in co_names
    # to their entry in the new co_names
    name_translations = dict((co_names.index(name), i)
                             for i, name in enumerate(names))

    # Build co_varnames for the new code object. This should consist of
    # the entirety of co_varnames with new_locals spliced in after the
    # arguments
    new_locals_len = len(new_locals)
    varnames = (co_varnames[:co_argcount] + new_locals +
                co_varnames[co_argcount:])

    # Build the dictionary that maps indices of entries in the old co_varnames
    # to their indices in the new co_varnames
    range1, range2 = xrange(co_argcount), xrange(co_argcount, len(co_varnames))
    varname_translations = dict((i, i) for i in range1)
    varname_translations.update((i, i + new_locals_len) for i in range2)

    # Build the dictionary that maps indices of deleted entries of co_names
    # to their indices in the new co_varnames
    names_to_varnames = dict((co_names.index(name), varnames.index(name))
                             for name in new_locals)

    # Now we modify the actual bytecode
    modified = []
    for inst in instructions(code_obj.co_code):
        # If the instruction is a LOAD_GLOBAL, we have to check to see if
        # it's one of the globals that we are replacing. Either way,
        # update its arg using the appropriate dict.
        if inst[0] == LOAD_GLOBAL:
            if inst[1] in names_to_varnames:
                inst[0] = LOAD_FAST
                inst[1] = names_to_varnames[inst[1]]
            elif inst[1] in name_translations:    
                inst[1] = name_translations[inst[1]]
            else:
                raise ValueError("a name was lost in translation")
        # If it accesses co_varnames or co_names then update its argument.
        elif inst[0] in opcode.haslocal:
            inst[1] = varname_translations[inst[1]]
        elif inst[0] in opcode.hasname:
            inst[1] = name_translations[inst[1]]
        modified.extend(write_instruction(inst))

    code = ''.join(modified)
    # Done modifying codestring - make the code object

    return types.CodeType(co_argcount + new_locals_len,
                          code_obj.co_nlocals + new_locals_len,
                          code_obj.co_stacksize,
                          code_obj.co_flags,
                          code,
                          code_obj.co_consts,
                          names,
                          varnames,
                          code_obj.co_filename,
                          code_obj.co_name,
                          code_obj.co_firstlineno,
                          code_obj.co_lnotab)


def instructions(code):
    code = map(ord, code)
    i, L = 0, len(code)
    extended_arg = 0
    while i < L:
        op = code[i]
        i+= 1
        if op < opcode.HAVE_ARGUMENT:
            yield [op, None]
            continue
        oparg = code[i] + (code[i+1] << 8) + extended_arg
        extended_arg = 0
        i += 2
        if op == opcode.EXTENDED_ARG:
            extended_arg = oparg << 16
            continue
        yield [op, oparg]

def write_instruction(inst):
    op, oparg = inst
    if oparg is None:
        return [chr(op)]
    elif oparg <= 65536L:
        return [chr(op), chr(oparg & 255), chr((oparg >> 8) & 255)]
    elif oparg <= 4294967296L:
        return [chr(opcode.EXTENDED_ARG),
                chr((oparg >> 16) & 255),
                chr((oparg >> 24) & 255),
                chr(op),
                chr(oparg & 255),
                chr((oparg >> 8) & 255)]
    else:
        raise ValueError("Invalid oparg: {0} is too large".format(oparg))


