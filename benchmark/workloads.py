POINT_LOOKUP = """
MATCH (u:User {id: $id})
RETURN u
"""

INDEXED_LOOKUP = """
MATCH (u:User)
WHERE u.id = $id
RETURN u
"""

TRAVERSAL_1_HOP = """
MATCH (u:User {id: $id})-[:VOTED]->(v)
RETURN count(v)
"""

TRAVERSAL_2_HOP = """
MATCH (u:User {id: $id})
      -[:VOTED]->()
      -[:VOTED]->(v)
RETURN count(v)
"""

TRAVERSAL_3_HOP = """
MATCH (u:User {id: $id})
      -[:VOTED]->()
      -[:VOTED]->()
      -[:VOTED]->(v)
RETURN count(v)
"""

AGGREGATION = """
MATCH (u:User)-[:VOTED]->()
RETURN u.id, count(*) AS votes
ORDER BY votes DESC
LIMIT 100
"""

WRITE_TICK = """
MATCH (u:User {id: $id})
SET u.benchmark_mark = $mark
"""

CREATE_USER_INDEX = """
CREATE INDEX user_id_index IF NOT EXISTS
FOR (u:User)
ON (u.id)
"""