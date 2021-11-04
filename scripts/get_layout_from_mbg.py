#!/usr/bin/python

import sys

mapping_file = sys.argv[1]
edge_overlap_file = sys.argv[2]
read_alignment_file = sys.argv[3]
paths_file = sys.argv[4]
output_readnames = sys.argv[5]
nodelens_file = sys.argv[6]
# layout to stdout

def revnode(n):
	assert len(n) >= 2
	assert n[0] == "<" or n[0] == ">"
	return (">" if n[0] == "<" else "<") + n[1:]

def canon(left, right):
	if revnode(right) + revnode(left) < left + right:
		return (revnode(right), revnode(left))
	return (left, right)

def get_leafs(path, mapping, edge_overlaps):
	result = path
	overlaps = []
	for i in range(1, len(path)):
		overlaps.append(edge_overlaps[canon(path[i-1], path[i])])
	while True:
		any_replaced = False
		new_result = []
		new_overlaps = []
		for i in range(0, len(result)):
			if result[i][1:] not in mapping:
				new_result.append(result[i])
				if i > 0: new_overlaps.append(overlaps[i-1])
			else:
				any_replaced = True
				part = mapping[result[i][1:]]
				if result[i][0] == "<":
					part = [revnode(n) for n in part[::-1]]
				new_result += part
				if i > 0: new_overlaps.append(overlaps[i-1])
				for j in range(1, len(part)):
					new_overlaps.append(edge_overlaps[canon(part[j-1], part[j])])
		assert len(new_result) == len(new_overlaps)+1
		assert len(new_result) >= len(result)
		if not any_replaced: break
		result = new_result
		overlaps = new_overlaps
	return (result, overlaps)

def get_match_len(path, pathstart, contigpath, contigstart, fw):
	match_len = 0
	while True:
		if pathstart < 0 or pathstart == len(path): break
		if contigstart < 0 or contigstart == len(contigpath): break
		if fw and path[pathstart] != contigpath[contigstart]: break
		if not fw and path[pathstart] != revnode(contigpath[contigstart]): break
		match_len += 1
		pathstart += 1
		if fw:
			contigstart += 1
		else:
			contigstart -= 1
	return match_len

def get_path_len(path, start, end, raw_node_lens, edge_overlaps):
	result = raw_node_lens[path[start][1:]]
	for i in range(1, len(path)):
		assert raw_node_lens[path[i][1:]] > edge_overlaps[canon(path[i-1], path[i])]
		result += raw_node_lens[path[i][1:]] - edge_overlaps[canon(path[i-1], path[i])]
	return result

def get_longest_matches(path, node_poses, contig_nodeseqs, raw_node_lens, edge_overlaps):
	longest = None
	also_longest = []
	for i in range(0, len(path)):
		if path[i][1:] not in node_poses: continue
		for startpos in node_poses[path[i][1:]]:
			(contig, index, fw) = startpos
			if path[i][0] == '<': fw = not fw
			assert (not fw) or contig_nodeseqs[contig][index] == path[i]
			assert (fw) or revnode(contig_nodeseqs[contig][index]) == path[i]
			match_node_len = get_match_len(path, i, contig_nodeseqs[contig], index, fw)
			assert match_node_len >= 1
			match_bp_len = get_path_len(path, i, i + match_node_len, raw_node_lens, edge_overlaps)
			if longest is None or match_bp_len > longest[0]:
				longest = (match_bp_len, contig, index, fw, i, match_node_len)
				also_longest = []
			elif longest is not None and match_bp_len == longest[0]:
				also_longest.append((match_bp_len, contig, index, fw, i, match_node_len))
	if longest is None: return []
	also_longest.append(longest)
	return also_longest
	return (longest[1], longest[2], longest[3], longest[4], longest[5])

node_mapping = {}
with open(mapping_file) as f:
	for l in f:
		parts = l.strip().split('\t')
		assert parts[0] not in node_mapping
		path = parts[1].replace('<', "\t<").replace('>', "\t>").strip().split('\t')
		node_mapping[parts[0]] = path

edge_overlaps = {}
with open(edge_overlap_file) as f:
	for l in f:
		parts = l.strip().split('\t')
		assert parts[0] == "L"
		fromnode = (">" if parts[2] == "+" else "<") + parts[1]
		tonode = (">" if parts[4] == "+" else "<") + parts[3]
		overlap = int(parts[5][:-1])
		key = canon(fromnode, tonode)
		if key in edge_overlaps: assert edge_overlaps[key] == overlap
		edge_overlaps[key] = overlap

raw_node_lens = {}
with open(nodelens_file) as f:
	for l in f:
		parts = l.strip().split('\t')
		assert parts[0] not in raw_node_lens or raw_node_lens[parts[0]] == int(parts[1])
		raw_node_lens[parts[0]] = int(parts[1])

contig_lens = {}
contig_nodeseqs = {}
contig_nodeoverlaps = {}
contig_node_offsets = {}
with open(paths_file) as f:
	for l in f:
		parts = l.strip().split('\t')
		pathname = parts[0]
		path = parts[1].replace('<', '\t<').replace('>', '\t>').strip().split('\t')
		(path, overlaps) = get_leafs(path, node_mapping, edge_overlaps)
		sys.stderr.write(pathname + "\t" + "".join(path) + "\n")
		contig_nodeseqs[pathname] = path
		contig_nodeoverlaps[pathname] = overlaps
		contig_node_offsets[pathname] = []
		contig_node_offsets[pathname].append(0)
		for i in range(1, len(path)):
			prev = path[i-1]
			curr = path[i]
			overlap = overlaps[i-1]
			nodelen = raw_node_lens[prev[1:]]
			contig_node_offsets[pathname].append(contig_node_offsets[pathname][-1] + nodelen - overlap)
		contig_lens[pathname] = contig_node_offsets[pathname][-1] + raw_node_lens[path[-1][1:]]

node_poses = {}
for contigname in contig_nodeseqs:
	for i in range(0, len(contig_nodeseqs[contigname])):
		nodename = contig_nodeseqs[contigname][i][1:]
		if contig_nodeseqs[contigname][i][0] == ">":
			if nodename not in node_poses: node_poses[nodename] = []
			node_poses[nodename].append((contigname, i, True))
		else:
			if nodename not in node_poses: node_poses[nodename] = []
			node_poses[nodename].append((contigname, i, False))

read_name_to_id = {}
next_read_id = 0

contig_contains_reads = {}
with open(read_alignment_file) as f:
	for l in f:
		parts = l.strip().split('\t')
		readname = parts[0]
		if readname not in read_name_to_id:
			read_name_to_id[readname] = next_read_id
			next_read_id += 1
		readlen = int(parts[1])
		readstart = int(parts[2])
		readend = int(parts[3])
		leftclip = int(parts[7])
		rightclip = int(parts[8])
		path = parts[5].replace('>', "\t>").replace('<', "\t<").strip().split('\t')
		longest_matches = get_longest_matches(path, node_poses, contig_nodeseqs, raw_node_lens, edge_overlaps)
		for match in longest_matches:
			(match_bp_size, contig, contigstart, fw, pathstart, matchlen) = match
			if fw:
				contigpos = contig_node_offsets[contig][contigstart]
				for i in range(0, pathstart):
					contigpos -= raw_node_lens[path[i][1:]] - edge_overlaps[canon(path[i], path[i+1])]
				contigpos += leftclip
				contigpos -= readstart
				if contig not in contig_contains_reads: contig_contains_reads[contig] = []
				contig_contains_reads[contig].append((readname, contigpos, contigpos + readlen))
			else:
				pathstart += matchlen - 1
				contigstart -= matchlen - 1
				assert pathstart < len(path)
				assert contigstart >= 0
				contigpos = contig_node_offsets[contig][contigstart]
				for i in range(pathstart+1, len(path)):
					contigpos -= raw_node_lens[path[i][1:]] - edge_overlaps[canon(path[i-1], path[i])]
				contigpos += rightclip
				contigpos -= readend
				if contig not in contig_contains_reads: contig_contains_reads[contig] = []
				contig_contains_reads[contig].append((readname, contigpos + readlen, contigpos))

for contig in contig_contains_reads:
	assert len(contig_contains_reads) > 0
	contig_contains_reads[contig].sort(key=lambda x: min(x[1], x[2]))
	actual_lines = []
	last_kept_read_pos = {}
	for line in contig_contains_reads[contig]:
		read_name = line[0]
		start_pos = min(line[1], line[2])
		end_pos = max(line[1], line[2])
		if read_name not in last_kept_read_pos:
			last_kept_read_pos[read_name] = (start_pos, end_pos)
		else:
			if start_pos < last_kept_read_pos[read_name][0] + 2000 and end_pos < last_kept_read_pos[read_name][1] + 2000:
				continue
		last_kept_read_pos[read_name] = (start_pos, end_pos)
		actual_lines.append(line)
	start_pos = actual_lines[0][1]
	end_pos = actual_lines[0][1]
	for line in actual_lines:
		start_pos = min(start_pos, line[1])
		start_pos = min(start_pos, line[2])
		end_pos = max(end_pos, line[1])
		end_pos = max(end_pos, line[2])
	print("tig\t" + contig)
	print("len\t" + str(end_pos - start_pos))
	print("cns")
	print("qlt")
	print("trimBgn\t0")
	print("trimEnd\t" + str(end_pos - start_pos))
	print("suggestRepeat\tF")
	print("suggestBubble\tF")
	print("suggestCircular\tF")
	print("circularLength\t0")
	print("numChildren\t" + str(len(contig_contains_reads[contig])))
	for line in actual_lines:
		print("read\t" + str(read_name_to_id[line[0]]) + "\tanchor\t0\thang\t0\t0\tposition" + "\t" + str(line[1] - start_pos) + "\t" + str(line[2] - start_pos))
	print("tigend")

with open(output_readnames, "w") as f:
	for name in read_name_to_id:
		f.write(name + "\t" + str(read_name_to_id[name]) + "\n")
