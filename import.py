#!/usr/bin/python 

dbhost = 'localhost'
dbuser = 'user'
dbpass = 'password'

dbname = 'database'

new_install_path = '/directory/leading/to/config'
new_install_url  = 'http://www.newblog.com'

old_site_url = 'http://www.oldblog.com/'
xml_file     = 'yourexportfile.xml'

import sys
from xml.dom import minidom
import MySQLdb as mdb
import re
import os
import subprocess



# XML handling functions

def getString( dom_tag ):
  rc = []
  for node in dom_tag:
    if node.nodeType == node.TEXT_NODE:
      rc.append(node.data)
  return ''.join(rc)

def getTag( tag, item ):
  nodelist = item.getElementsByTagName( tag )[0].childNodes
  return getString( nodelist ) 

def getEncodedTag( tag, item ):
  if item.getElementsByTagName(tag)[0].firstChild:
    send_back =  item.getElementsByTagName(tag)[0].firstChild.wholeText
  else:
    send_back  = ''
  return removeUnicode( send_back )

def getPostTerms( item ):
  terms = []
  for term in item.getElementsByTagName( 'category' ):
    if term.getAttributeNode('domain'):
      domain = term.getAttributeNode('domain').value
    else:
      domain = ''

    prettyname = term.firstChild.wholeText

    if term.getAttributeNode('nicename'):
      slugname = term.getAttributeNode('nicename').value
    else:
      slugname = ''

    terms.append( [ domain, prettyname, slugname ] )
  return terms

def getPostMeta( item ):
  postmeta = []
  for meta in item.getElementsByTagName( 'wp:postmeta' ):
    meta_key   = getString( meta.getElementsByTagName( 'wp:meta_key' )[0].childNodes )
    if meta.getElementsByTagName( 'wp:meta_value' )[0].firstChild:
      meta_value = removeUnicode( meta.getElementsByTagName( 'wp:meta_value' )[0].firstChild.wholeText )
    else:
      meta_value = ''
    postmeta.append( [ meta_key, meta_value] )  
  return postmeta
    
    
#Misc Funcs

def removeUnicode( string ):
  string = string.replace(u'\xa0', u' ')
  string = string.replace(u'\u2019', u' ')
  string = string.replace(u'\u2013', u' ')
  string = string.replace(u'\u2014', u' ')
  string = string.replace(u'\u201c', u' ')
  string = string.replace(u'\u201d', u' ')
  string = string.replace(u'\u2019', u' ')
  string = string.replace(u'\u2026', u' ')
  string = string.replace(u'\u2018', u' ')
  string = string.replace(u'\u2033', u' ')
  return string


# Wordpress Handing Functions

def WPhandlePost( post ):
  global cur
  post = WPcleanAndValidatePostData( post )

  new_post_id = WPwritePost( post ) 

  WPhandleTerms( new_post_id, post['terms'] )
  WPhandlePostMeta( new_post_id, post['post_meta'])
  WPhandleImages( new_post_id, post )

def WPcleanAndValidatePostData( post ):
  if post['post_modified'] == '':
    post['post_modified'] = post['post_date']

  if post['post_modified_gmt'] == '':
    post['post_modified_gmt'] = post['post_date_gmt']

  post['post_content'] = post['post_content'].encode('utf-8')
  post['post_excerpt'] = post['post_excerpt'].encode('utf-8')

  post['post_title']   = removeUnicode( post['post_title'] )

  if post['post_excerpt'] == '':
    post['post_excerpt'] = post['post_content']

  if isinstance( post['post_author'], int ) == False:
    post['post_author'] = WPgetAuthorByDisplayName( post['post_author'] )

  return post



  # Creates Categories and / or Tags as needed
  # terms ex: [ ['tag', 'Big Houses', 'big-houses'], ['category', 'New Listings', 'new-listings'] ]

def WPwritePost( post ):
  insert_post_sql = "INSERT INTO %s.wp_posts " % ( dbname )
  insert_post_sql += "( post_author, post_date, post_date_gmt, post_content, post_title, post_status, comment_status, ping_status, post_name, post_modified, post_modified_gmt, post_parent, guid, menu_order, post_type, post_mime_type, comment_count ) "
  insert_post_sql += 'VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s );'  
  cur.execute( insert_post_sql, ( post['post_author'], post['post_date'], post['post_date_gmt'], post['post_content'], post['post_title'], post['post_status'], post['comment_status'], post['ping_status'], post['post_name'], post['post_modified'], post['post_modified_gmt'], post['post_parent'], post['guid'], post['menu_order'], post['post_type'], post['post_mime_type'], 0 ) )

  get_id = 'SELECT ID FROM %s.wp_posts WHERE post_name = "%s" ORDER BY ID DESC LIMIT 1' % ( dbname, post['post_name'] )
  cur.execute( get_id )
  new_post_id = cur.fetchall()[0][0]
  return new_post_id


# @name: WPhandleImages
#
# @desc: Takes all terms ( category/tags ) associated with a post
#        and creates the Wordpress entrys if needed, then makes the appropriate associations
#
# @params: 
#     post_id   : int()  :  the new post_id for the new blog
#     post      : dict{} :  

def WPhandleImages( post_id, post ):
  global old_site_url
  global new_install_path
  global new_install_url
  upload_dir = new_install_path + 'wp-content/uploads/'

  for a in list(re.finditer( old_site_url, post['post_content'] ) ):
    url_find = post['post_content'] [a.start() : len( post['post_content'] ) ]
    url_find = url_find.split( ' ', 1 )
    url_find = url_find[0].replace( '"', '')
    old_img_url = url_find.replace( "'", '')
    old_img_url_segs =  old_img_url.split('/')

    seg_cnt = 0
    for seg in old_img_url_segs:
      if len( seg ) == 4 and seg.isdigit():
        image_year  = seg
        image_month = old_img_url_segs[seg_cnt+1]
        image_upload_dir = upload_dir + image_year + '/' + image_month

        the_file = old_img_url_segs[seg_cnt+2]

        # @todo: finish the accepted extensions poriton
        acceptable_extensions = ['jpg', 'jpeg', 'gif', 'png', 'pdf', 'mp3']
        extension = old_img_url_segs
        file_xploded = the_file.split('.')

        if file_xploded[ len(file_xploded) - 1 ]  in acceptable_extensions:
          try:
              os.makedirs(image_upload_dir)
          except OSError,err:
              if err.errno!=17:
                  raise

          if os.path.exists( image_upload_dir + '/' + the_file ) == False:
            subprocess.call("wget -P %s %s" % ( image_upload_dir, old_img_url ), shell=True)
          
          new_image_url = new_install_url + 'wp-content/uploads/%s/%s/%s' % ( image_year, image_month, the_file )
          WPlinkImages( post_id, post, new_image_url, file_xploded[ 0: -1 ], file_xploded[ len(file_xploded) - 1 ] )

          break

        # @todo search extensions here to make sure we're only getting files we want.


      seg_cnt += 1

def WPlinkImages( post_id, text_post, uri, fileName, ext ):
  wp_post_image = {
    'post_author'          : text_post['post_author'],
    'post_date'            : text_post['post_date'],
    'post_date_gmt'        : text_post['post_date_gmt'],
    'post_content'         : '',
    'post_title'           : fileName[0],
    'post_excerpt'         : '',
    'post_status'          : 'inherit',
    'comment_status'       : 'open',
    'ping_status'          : 'open',
    'post_password'        : '',
    'post_name'            : text_post['post_name'],
    'to_ping'              : '',
    'pinged'               : '',
    'post_modified'        : text_post['post_modified'],
    'post_modified_gmt'    : text_post['post_modified_gmt'],
    'post_content_filterd' : '',
    'post_parent'          : post_id, 
    'guid'                 : uri, 
    'menu_order'           : '0',
    'post_type'            : 'attatchment',
    'post_mime_type'       : 'image/' + ext.lower(),
    'terms'                : [],
    'post_meta'            : []
  }

  WPwritePost( wp_post_image )


# @name: WPhandleTerms
#
# @desc: Takes all terms ( category/tags ) associated with a post
#        and creates the Wordpress entrys if needed, then makes the appropriate associations
#
# @params: 
#     post_id   : int()  :  the new post_id for the new blog
#     post_meta : list() :  [ [ domain, prettyname, slugname ], [ 'category', 'New Lisitings', 'new-listings'] ]

def WPhandleTerms( post_id, terms ):
  global cur
  global added_tags
  for term in terms:
    if len( term[0] ):
      if term[2] == '':
        term[2] = WPcreateSlug( term[1] )
      term[1] = removeUnicode( term[1] )
      term[2] = removeUnicode( term[2] )
      check_exists_sql = "SELECT * FROM %s.wp_terms WHERE slug = '%s'" % ( dbname, term[2] )
      cur.execute(check_exists_sql)
      check = cur.fetchall()

      # Make the Term if it doesnt exisit
      if len( check ) == 0:
        insert_terms = 'INSERT INTO %s.wp_terms ( name, slug, term_group ) VALUES ( "%s", "%s", 0 ) ' % ( dbname, term[1], term[2] )
        cur.execute( insert_terms )
        get_id = 'SELECT term_id FROM %s.wp_terms WHERE name = "%s" AND slug = "%s" LIMIT 1' % ( dbname, term[1], term[2] )
        cur.execute( get_id )
        term_id = cur.fetchall()[0][0]

        insert_term_tax = 'INSERT INTO %s.wp_term_taxonomy (term_id, taxonomy, description, parent, count ) VALUES( "%s", "%s", "", 0, 0 )' % ( dbname, term_id, term[0] )
        cur.execute( insert_term_tax )

      # We've got the term, get its info
      else:
        term_id   = check[0][0]
        term_name = check[0][1]

      get_tax_id = 'SELECT term_taxonomy_id FROM %s.wp_term_taxonomy WHERE term_id = "%s" LIMIT 1' % ( dbname, term_id )
      cur.execute( get_tax_id )
      term_taxonomy_id = cur.fetchall()[0][0]

      # Check for a  Link, if theres not make it
      check_relationship = 'SELECT * FROM  %s.wp_term_relationships WHERE object_id = "%s" AND term_taxonomy_id = "%s";' % ( dbname, post_id, term_taxonomy_id ) 
      cur.execute( check_relationship )
      relationship = cur.fetchall()

      if len( relationship ) == 0:
        insert_term_relationship = 'INSERT INTO %s.wp_term_relationships ( object_id, term_taxonomy_id, term_order ) VALUES( "%s", "%s", 0 )' % ( dbname, post_id, term_taxonomy_id )
        cur.execute( insert_term_relationship )


# @name: WPhandlePostMeta
# 
# @desc:
# 
# @params: 
#     post_id   : int()  :  the new post_id for the new blog
#     post_meta : list() :  [ [ meta_key, meta_value ], [ 'views', '20' ] ]

def WPhandlePostMeta( post_id, post_meta ):
  global cur
  for meta in post_meta:
    insert_terms = 'INSERT INTO %s.wp_postmeta ( post_id, meta_key, meta_value ) ' % dbname
    cur.execute( insert_terms + 'VALUES ( %s, %s, %s ) ', ( post_id, meta[0], meta[1] ) )


def WPgetAuthorByDisplayName( display_name ):
  global cur
  cur.execute( 'SELECT ID FROM %s.wp_users WHERE display_name = "%s"' % ( dbname, display_name ) )
  found = cur.fetchall()
  if len( found ) > 0:
    author_id = found[0][0]
  else:
    author_id = 1
  return author_id


def WPcreateSlug( butterfly ):
  string = butterfly.lower()
  string = string.replace('!', '')
  string = string.replace('@', '')
  string = string.replace('#', '')
  string = string.replace('$', '')
  string = string.replace('%', '')  
  string = string.replace('^', '')
  string = string.replace('*', '')
  string = string.replace('#', '')  
  string = string.replace('(', '')
  string = string.replace(')', '')
  string = string.replace('=', '')
  string = string.replace('+', '')
  string = string.replace('~', '')
  string = string.replace('`', '')  
  string = string.replace('/', '')
  string = string.replace('.', '')
  string = string.replace(',', '')
  string = string.replace('<', '')  
  string = string.replace('>', '')
  string = string.replace('?', '')  
  string = string.replace('\\', '')
  string = string.replace('[', '')  
  string = string.replace(']', '')    
  string = string.replace('{', '')      
  string = string.replace('}', '')
  string = string.replace('"', '')  
  string = string.replace("'", "")    
  string = string.replace('|', '')
  string = string.replace('&', 'and')
  string = string.replace('---', '-')
  string = string.replace(' ', '-')
  return string



# WORDPRESS XML VERSION 1.0
xmldoc = minidom.parse( xml_file )
itemlist = xmldoc.getElementsByTagName('item')

# @todo: actually use these vars and get some sort of print out back to the user
added_tags    = 0
added_cats    = 0
added_posts   = 0
added_authors = 0

con = mdb.connect( dbhost, dbuser, dbpass )
cur = con.cursor()



# Loop through all items in the XML back-up
for item in itemlist:
  post_status = getTag('wp:status', item)
  post_type   = getTag('wp:post_type', item)

  if post_status == 'publish' and post_type == 'post':
    # WP_POSTS TABLE ITEMS
    wp_post = {
      'post_id'              : getTag('wp:post_id', item),                      #| orignal post id
      'post_author'          : getEncodedTag('dc:creator', item),               #| @todo MAKE DYNAMIC, currently static because the current import is static
      'post_date'            : getTag('wp:post_date', item),                    #|
      'post_date_gmt'        : getTag('wp:post_date_gmt', item),
      'post_content'         : getEncodedTag('content:encoded', item),          #| ALL sorts of hacks to get this to work...
      'post_title'           : getTag('title', item),
      'post_excerpt'         : getEncodedTag('excerpt:encoded', item),
      'post_status'          : getTag('wp:status', item),
      'comment_status'       : getTag('wp:comment_status', item),
      'ping_status'          : getTag('wp:ping_status', item),
      'post_password'        : '',                                               #| Ommitted because there is no current use for my purposes
      'post_name'            : getTag('wp:post_name', item),                     
      'to_ping'              : '',                                               #| Omitted because this should be handled before import.
      'pinged'               : '',                                               #| Omitted, cant find in export
      'post_modified'        : '',                                               #| Omitted, cant find in export
      'post_modified_gmt'    : '',                                               #| Omitted, cant find in export
      'post_content_filterd' : '',                                               #| Omitted, not sure what to do with this
      'post_parent'          : getTag('wp:post_parent', item), 
      'guid'                 : getTag('guid', item), 
      'menu_order'           : getTag('wp:menu_order', item),                    #| Probably won't need for my purposes, but its easy
      'post_type'            : getTag('wp:post_type', item),                     
      'post_mime_type'       : '',                                               #| For posts this is always an empty string
      'terms'                : getPostTerms( item ),
      'post_meta'            : getPostMeta( item )
    }

    print 'POST ID: %s' % wp_post['post_id']

    WPhandlePost( wp_post )
