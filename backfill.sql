UPDATE re_properties 
SET ref_code = external_id 
WHERE (ref_code IS NULL OR ref_code = '') 
  AND external_id IS NOT NULL 
  AND length(trim(external_id)) BETWEEN 2 AND 10;
