
# Copyright (c) 2013, Kevin Greenan (kmgreen2@gmail.com)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# Redistributions in binary form must reproduce the above copyright notice, this
# list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.  THIS SOFTWARE IS PROVIDED BY
# THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import pyeclib_c
import math

class ECPyECLibDriver(object):
  def __init__(self, k, m, type):
    self.ec_rs_vand = "rs_vand"
    self.ec_rs_cauchy_orig = "rs_cauchy_orig"
    self.ec_flat_xor_3 = "flat_xor_3"
    self.ec_flat_xor_4 = "flat_xor_4"
    self.ec_types = [self.ec_rs_vand, self.ec_rs_cauchy_orig, self.ec_flat_xor_3, self.ec_flat_xor_4]
    self.ec_valid_xor_params = ["12_6_4", "10_5_3"]
    self.ec_rs_vand_best_w = 16
    self.ec_default_w = 32
    self.ec_rs_cauchy_best_w = 4
    self.k = k
    self.m = m
    if type in self.ec_types:
      self.type = type
    else:
      raise ECDriverError("%s is not a valid EC type for PyECLib!")

    if self.type == self.ec_rs_vand:
      self.w = self.ec_rs_vand_best_w
      self.hd = self.m + 1
    elif self.type == self.ec_rs_cauchy_orig:
      self.w = self.ec_rs_cauchy_best_w
      self.hd = self.m + 1
    elif self.type == self.ec_flat_xor_3:
      self.w = self.ec_default_w
      self.hd = 3
    elif self.type == self.ec_flat_xor_4:
      self.w = self.ec_default_w
      self.hd = 4
    else:
      self.w = self.ec_default_w

    self.handle = pyeclib_c.init(self.k, self.m, self.w, self.type)

  def encode(self, bytes):
    return pyeclib_c.encode(self.handle, bytes) 
  
  def decode(self, fragment_payloads):
    try:
      ret_string = pyeclib_c.fragments_to_string(self.handle, fragment_payloads)
    except:
      raise ECDriverError("Error in ECPyECLibDriver.decode")

    if ret_string is None:
      (data_frags, parity_frags, missing_idxs) = pyeclib_c.get_fragment_partition(self.handle, fragment_payloads)
      decoded_fragments = pyeclib_c.decode(self.handle, data_frags, parity_frags, missing_idxs, len(data_frags[0]))
      ret_string = pyeclib_c.fragments_to_string(self.handle, decoded_fragments)

    return ret_string
  
  def reconstruct(self, fragment_payloads, indexes_to_reconstruct):
    reconstructed_bytes = []

    # Reconstruct the data, then the parity
    # The parity cannot be reconstructed until
    # after all data is reconstructed
    indexes_to_reconstruct.sort()
    _indexes_to_reconstruct = indexes_to_reconstruct[:]

    while len(_indexes_to_reconstruct) > 0:
      index = _indexes_to_reconstruct.pop(0)
      (data_frags, parity_frags, missing_idxs) = pyeclib_c.get_fragment_partition(self.handle, fragment_payloads)
      reconstructed = pyeclib_c.reconstruct(self.handle, data_frags, parity_frags, missing_idxs, index, len(data_frags[0]))
      reconstructed_bytes.append(reconstructed)

    return reconstructed_bytes

  def fragments_needed(self, missing_fragment_indexes):
    return pyeclib_c.get_required_fragments(missing_fragment_indexes) 

  def get_metadata(self, fragment):
    pass

  def verify_stripe_metadata(self, fragment_metadata_list):
    pass

class ECNullDriver(object):
  def __init__(self, k, m):
    self.k = k
    self.m = m

  def encode(self, bytes):
    pass
  
  def decode(self, fragment_payloads):
    pass
  
  def reconstruct(self, available_fragment_payloads, missing_fragment_indexes):
    pass

  def fragments_needed(self, missing_fragment_indexes):
    pass

  def get_metadata(self, fragment):
    pass

  def verify_stripe_metadata(self, fragment_metadata_list):
    pass


#
# A striping-only driver for EC.  This is
# pretty much RAID 0.
#
class ECStripingDriver(object):
  def __init__(self, k, m):
    """
    Stripe an arbitrary-sized string into k fragments
    :param k: the number of data fragments to stripe
    :param m: the number of parity fragments to stripe
    :raises: ECDriverError if there is an error during encoding
    """
    self.k = k

    if m != 0:
      raise ECDriverError("This driver only supports m=0")

    self.m = m

  def encode(self, bytes):
    """
    Stripe an arbitrary-sized string into k fragments
    :param bytes: the buffer to encode
    :returns: a list of k buffers (data only)
    :raises: ECDriverError if there is an error during encoding
    """
    # Main fragment size
    fragment_size = math.ceil(len(bytes) / float(self.k))

    # Size of last fragment
    last_fragment_size = len(bytes) - (fragment_size*self.k-1)

    fragments = []
    offset = 0
    for i in range(self.k-1):
      fragments.append(bytes[offset:fragment_size])
      offset += fragment_size

    fragments.append(bytes[offset:last_fragment_size])

    return fragments
  
  def decode(self, fragment_payloads):
    """
    Convert a k-fragment data stripe into a string 
    :param fragment_payloads: fragments (in order) to convert into a string
    :returns: a string containing the original data
    :raises: ECDriverError if there is an error during decoding
    """

    if len(fragment_payloads) != self.k:
      raise ECDriverError("Decode requires %d fragments, %d fragments were given" % (len(fragment_payloads), self.k))

    ret_string = ''

    for fragment in fragment_payloads:
      ret_string += fragment 

    return ret_string
  
  def reconstruct(self, available_fragment_payloads, missing_fragment_indexes):
    """
    We cannot reconstruct a fragment using other fragments.  This means that
    reconstruction means all fragments must be specified, otherwise we cannot
    reconstruct and must raise an error.
    :param available_fragment_payloads: available fragments (in order) 
    :param missing_fragment_indexes: indexes of missing fragments
    :returns: a string containing the original data
    :raises: ECDriverError if there is an error during reconstruction
    """
    if len(available_fragment_payloads) != self.k:
      raise ECDriverError("Reconstruction requires %d fragments, %d fragments were given" % (len(available_fragment_payloads), self.k))

    return available_fragment_payloads

  def fragments_needed(self, missing_fragment_indexes):
    """
    By definition, all missing fragment indexes are needed to reconstruct,
    so just return the list handed to this function.
    :param missing_fragment_indexes: indexes of missing fragments
    :returns: missing_fragment_indexes
    """
    return missing_fragment_indexes 

  def get_metadata(self, fragment):
    """
    This driver does not include fragment metadata, so return an empty string
    :param fragment: a fragment
    :returns: empty string
    """
    return '' 

  def verify_stripe_metadata(self, fragment_metadata_list):
    """
    This driver does not include fragment metadata, so return true
    :param fragment_metadata_list: a list of fragments
    :returns: True 
    """
    return True 