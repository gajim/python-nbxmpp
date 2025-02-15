def xml2str_sorted(data):
    s = "<" + data.name
    if data.namespace:
        if not data.parent or data.parent.namespace != data.namespace:
            if "xmlns" not in data.attrs:
                s += ' xmlns="%s"' % data.namespace
    for key in sorted(data.attrs.keys()):
        val = str(data.attrs[key])
        s += ' %s="%s"' % (key, val)

    s += ">"
    cnt = 0
    if data.kids:
        for a in data.kids:
            if (len(data.data) - 1) >= cnt:
                s += data.data[cnt]
            if isinstance(a, str):
                s += a.__str__()
            else:
                s += xml2str_sorted(a)
            cnt += 1
    if (len(data.data) - 1) >= cnt:
        s += data.data[cnt]
    if not data.kids and s.endswith(">"):
        s = s[:-1] + " />"
    else:
        s += "</" + data.name + ">"
    return s
